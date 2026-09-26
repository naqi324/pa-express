import asyncio
import secrets
import time
from dataclasses import dataclass, field

from pydantic import SecretStr

from .config import Settings
from .schemas import (
    ClaudeConfig,
    ClaudeConfigInput,
    OpenAiGptConfig,
    OpenAiGptConfigInput,
    RuntimeCapabilities,
)
from .services.case_store import CaseStore


def mask_secret_hint(value: str) -> str:
    """Return the last four characters of a secret, never enough to reuse it."""
    if len(value) <= 8:
        return "set"
    return f"…{value[-4:]}"


def runtime_capabilities(settings: Settings) -> RuntimeCapabilities:
    return RuntimeCapabilities(
        anthropic_claude_enabled=settings.claude_enabled,
        openai_gpt_enabled=settings.openai_gpt_enabled,
    )


class EngineConfigStore:
    """Per-session provider overrides for Claude and OpenAI GPT.

    Secrets are write-only. A blank key in a later save keeps the stored key;
    clearing the override drops every secret it held.
    """

    def __init__(self) -> None:
        self._claude: ClaudeConfigInput | None = None
        self._openai_gpt: OpenAiGptConfigInput | None = None
        self._lock = asyncio.Lock()

    async def set_claude(self, config: ClaudeConfigInput) -> None:
        async with self._lock:
            previous = self._claude
            if previous is not None:
                updates: dict[str, str | None] = {}
                if config.api_key is None:
                    updates["api_key"] = previous.api_key
                if not (config.aws_access_key_id and config.aws_secret_access_key):
                    # A new key pair replaces the whole triple; otherwise keep the stored one.
                    updates["aws_access_key_id"] = previous.aws_access_key_id
                    updates["aws_secret_access_key"] = previous.aws_secret_access_key
                    updates["aws_session_token"] = previous.aws_session_token
                config = config.model_copy(update=updates)
            self._claude = config

    async def clear_claude(self) -> None:
        async with self._lock:
            self._claude = None

    async def set_openai_gpt(self, config: OpenAiGptConfigInput) -> None:
        async with self._lock:
            previous = self._openai_gpt
            if previous is not None and config.api_key is None:
                config = config.model_copy(update={"api_key": previous.api_key})
            self._openai_gpt = config

    async def clear_openai_gpt(self) -> None:
        async with self._lock:
            self._openai_gpt = None

    def claude_view(self, settings: Settings) -> ClaudeConfig:
        effective = self.effective_settings(settings)
        api_key = effective.anthropic_api_key.get_secret_value()
        return ClaudeConfig(
            auth_method=effective.claude_auth_method,
            model_id=effective.claude_model_id,
            effort=effective.claude_effort,
            command=effective.claude_command,
            api_key_hint=mask_secret_hint(api_key) if api_key else None,
            api_key_configured=bool(api_key),
            bedrock_region=effective.bedrock_region,
            bedrock_credentials=effective.bedrock_credentials,
            aws_profile=effective.aws_profile,
            access_key_id_hint=(
                mask_secret_hint(effective.aws_access_key_id)
                if effective.aws_access_key_id
                else None
            ),
            access_keys_configured=bool(
                effective.aws_access_key_id and effective.aws_secret_access_key
            ),
            is_override=self._claude is not None,
        )

    def openai_gpt_view(self, settings: Settings) -> OpenAiGptConfig:
        effective = self.effective_settings(settings)
        api_key = effective.openai_api_key.get_secret_value()
        return OpenAiGptConfig(
            auth_method=effective.openai_gpt_auth_method,
            model_id=effective.openai_gpt_model_id,
            effort=effective.openai_gpt_effort,
            command=effective.codex_command,
            api_key_hint=mask_secret_hint(api_key) if api_key else None,
            api_key_configured=bool(api_key),
            is_override=self._openai_gpt is not None,
        )

    def effective_settings(self, settings: Settings) -> Settings:
        """Return Settings with this session's engine overrides applied.

        The routes validate model and effort against the catalog before they
        store an override, so the copy skips Settings validation safely.
        """
        updates: dict[str, object] = {}
        claude = self._claude
        if claude is not None:
            updates.update(
                claude_auth_method=claude.auth_method,
                claude_model_id=claude.model_id,
                claude_effort=claude.effort,
                bedrock_region=claude.bedrock_region,
                bedrock_credentials=claude.bedrock_credentials,
            )
            if claude.api_key:
                updates["anthropic_api_key"] = SecretStr(claude.api_key)
            if claude.aws_profile:
                updates["aws_profile"] = claude.aws_profile
            if claude.aws_access_key_id and claude.aws_secret_access_key:
                updates["aws_access_key_id"] = claude.aws_access_key_id
                updates["aws_secret_access_key"] = claude.aws_secret_access_key
                updates["aws_session_token"] = claude.aws_session_token or ""
        openai_gpt = self._openai_gpt
        if openai_gpt is not None:
            updates.update(
                openai_gpt_auth_method=openai_gpt.auth_method,
                openai_gpt_model_id=openai_gpt.model_id,
                openai_gpt_effort=openai_gpt.effort,
            )
            if openai_gpt.api_key:
                updates["openai_api_key"] = SecretStr(openai_gpt.api_key)
        if not updates:
            return settings
        return settings.model_copy(update=updates)


@dataclass
class SessionState:
    engine_config: EngineConfigStore = field(default_factory=EngineConfigStore)
    cases: CaseStore = field(default_factory=CaseStore)
    last_seen_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_seen_at = time.time()


class SessionManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, session_id: str | None) -> tuple[str, SessionState, bool]:
        async with self._lock:
            self._purge_expired_locked()
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                session.touch()
                return session_id, session, False

            new_session_id = secrets.token_urlsafe(32)
            session = SessionState()
            self._sessions[new_session_id] = session
            session.touch()
            return new_session_id, session, True

    def _purge_expired_locked(self) -> None:
        cutoff = time.time() - (self.settings.session_idle_minutes * 60)
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.last_seen_at < cutoff
        ]
        for session_id in expired:
            del self._sessions[session_id]
