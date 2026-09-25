import asyncio
import secrets
import time
from dataclasses import dataclass, field

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
    """Return a short, non-reversible hint for a key id (never the full value)."""
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}...{value[-3:]}"


def runtime_capabilities(settings: Settings) -> RuntimeCapabilities:
    return RuntimeCapabilities(
        anthropic_claude_enabled=settings.bedrock_enabled,
        openai_gpt_enabled=settings.codex_enabled,
    )


class EngineConfigStore:
    """Per-session provider overrides for Claude and OpenAI GPT."""

    def __init__(self) -> None:
        self._claude: ClaudeConfigInput | None = None
        self._openai_gpt: OpenAiGptConfigInput | None = None
        self._lock = asyncio.Lock()

    async def set_claude(self, config: ClaudeConfigInput) -> None:
        async with self._lock:
            if (
                self._claude is not None
                and config.auth_method == "access_keys"
                and not (config.aws_access_key_id and config.aws_secret_access_key)
            ):
                config = config.model_copy(
                    update={
                        "aws_access_key_id": self._claude.aws_access_key_id,
                        "aws_secret_access_key": self._claude.aws_secret_access_key,
                        "aws_session_token": self._claude.aws_session_token,
                    }
                )
            self._claude = config

    async def clear_claude(self) -> None:
        async with self._lock:
            self._claude = None

    async def set_openai_gpt(self, config: OpenAiGptConfigInput) -> None:
        async with self._lock:
            self._openai_gpt = config

    async def clear_openai_gpt(self) -> None:
        async with self._lock:
            self._openai_gpt = None

    def claude_view(self, settings: Settings) -> ClaudeConfig:
        override = self._claude
        if override is None:
            return ClaudeConfig(
                auth_method=settings.bedrock_auth_method,
                region=settings.bedrock_region,
                model_id=settings.bedrock_model_id,
                effort=settings.bedrock_effort,
                aws_profile=settings.aws_profile,
                access_key_id_hint=(
                    mask_secret_hint(settings.aws_access_key_id)
                    if settings.aws_access_key_id
                    else None
                ),
                access_keys_configured=bool(
                    settings.aws_access_key_id and settings.aws_secret_access_key
                ),
                is_override=False,
            )
        return ClaudeConfig(
            auth_method=override.auth_method,
            region=override.region,
            model_id=override.model_id,
            effort=override.effort,
            aws_profile=override.aws_profile or settings.aws_profile,
            access_key_id_hint=(
                mask_secret_hint(override.aws_access_key_id or settings.aws_access_key_id)
                if override.aws_access_key_id or settings.aws_access_key_id
                else None
            ),
            access_keys_configured=bool(
                (override.aws_access_key_id and override.aws_secret_access_key)
                or (settings.aws_access_key_id and settings.aws_secret_access_key)
            ),
            is_override=True,
        )

    def openai_gpt_view(self, settings: Settings) -> OpenAiGptConfig:
        override = self._openai_gpt
        if override is None:
            return OpenAiGptConfig(
                command=settings.codex_command,
                model_id=settings.codex_model_id,
                effort=settings.codex_effort,
                is_override=False,
            )
        return OpenAiGptConfig(
            command=override.command,
            model_id=override.model_id,
            effort=override.effort,
            is_override=True,
        )

    def effective_settings(self, settings: Settings) -> Settings:
        """Return Settings with this session's engine overrides applied."""
        updates: dict[str, object] = {}
        claude = self._claude
        if claude is not None:
            updates.update(
                bedrock_auth_method=claude.auth_method,
                bedrock_region=claude.region,
                bedrock_model_id=claude.model_id,
                bedrock_effort=claude.effort,
            )
            if claude.aws_profile:
                updates["aws_profile"] = claude.aws_profile
            if claude.aws_access_key_id and claude.aws_secret_access_key:
                updates["aws_access_key_id"] = claude.aws_access_key_id
                updates["aws_secret_access_key"] = claude.aws_secret_access_key
                updates["aws_session_token"] = claude.aws_session_token or ""
        openai_gpt = self._openai_gpt
        if openai_gpt is not None:
            updates["codex_command"] = openai_gpt.command
            updates["codex_model_id"] = openai_gpt.model_id
            updates["codex_effort"] = openai_gpt.effort
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
