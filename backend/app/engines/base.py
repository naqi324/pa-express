"""Engine abstraction + registry with cheap availability checks and rules-engine fallback."""

import shutil
from abc import ABC, abstractmethod

from ..config import Settings
from ..schemas import Determination, EngineId, EngineInfo, PARequest


class Engine(ABC):
    id: EngineId
    label: str
    description: str
    model_id: str | None = None

    @abstractmethod
    async def evaluate(
        self,
        request: PARequest,
        scenario: dict,
        settings: Settings,
    ) -> Determination:
        """Produce a Determination for the request against its scenario policy."""

    def availability(self, settings: Settings) -> tuple[bool, str]:
        """Cheap availability probe: (available, availability_note). Never blocks."""
        return True, ""


class RubricEngineBase(Engine):
    id: EngineId = "offline"
    label = "Rules engine"
    description = (
        "Checks the case facts against each policy criterion. No model or network call."
    )


def claude_method_readiness(settings: Settings, method: str) -> tuple[bool, str]:
    """Cheap readiness probe for one Claude auth method. Never calls the provider."""
    if method == "cli":
        if shutil.which(settings.claude_command) is None:
            return False, f"The '{settings.claude_command}' CLI was not found on PATH."
        return True, f"Runs the local '{settings.claude_command}' CLI with its own sign-in."
    if method == "api_key":
        if not settings.anthropic_api_key.get_secret_value():
            return False, "Enter an Anthropic API key to use this method."
        return True, "Uses the Anthropic API key held for this session."
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False, "boto3 is not installed in this environment."
    if settings.bedrock_credentials == "access_keys":
        if not (settings.aws_access_key_id and settings.aws_secret_access_key):
            return False, "AWS access keys are selected but not yet entered for this session."
        return True, f"Uses session AWS access keys in {settings.bedrock_region}."
    if settings.aws_profile:
        return True, f"Uses AWS profile {settings.aws_profile} in {settings.bedrock_region}."
    return True, f"Uses the default AWS credential chain in {settings.bedrock_region}."


def openai_gpt_method_readiness(settings: Settings, method: str) -> tuple[bool, str]:
    """Cheap readiness probe for one OpenAI GPT auth method. Never calls the provider."""
    if method == "api_key":
        if not settings.openai_api_key.get_secret_value():
            return False, "Enter an OpenAI API key to use this method."
        return True, "Uses the OpenAI API key held for this session."
    if shutil.which(settings.codex_command) is None:
        return False, f"The '{settings.codex_command}' CLI was not found on PATH."
    return True, f"Runs the local '{settings.codex_command}' CLI with its own sign-in."


def _claude_availability(settings: Settings) -> tuple[bool, str]:
    if not settings.claude_enabled:
        return False, "Anthropic Claude is disabled for this deployment."
    return claude_method_readiness(settings, settings.claude_auth_method)


def _openai_gpt_availability(settings: Settings) -> tuple[bool, str]:
    if not settings.openai_gpt_enabled:
        return False, "OpenAI GPT is disabled for this deployment."
    return openai_gpt_method_readiness(settings, settings.openai_gpt_auth_method)


class EngineRegistry:
    def __init__(self, engines: dict[str, Engine], fallback_id: str = "offline") -> None:
        self._engines = engines
        self._fallback_id = fallback_id

    def engine_ids(self) -> list[str]:
        return list(self._engines.keys())

    def get(self, engine_id: str) -> Engine:
        engine = self._engines.get(engine_id)
        if engine is None:
            from ..errors import AppError

            raise AppError(
                404,
                "ENGINE_NOT_FOUND",
                f"Unknown evaluation engine '{engine_id}'.",
                "Choose one of: offline, anthropic_claude, openai_gpt.",
            )
        return engine

    def is_available(self, engine: Engine, settings: Settings) -> tuple[bool, str]:
        if engine.id == "anthropic_claude":
            return _claude_availability(settings)
        if engine.id == "openai_gpt":
            return _openai_gpt_availability(settings)
        return engine.availability(settings)

    def list_engines(self, settings: Settings) -> list[EngineInfo]:
        infos: list[EngineInfo] = []
        for engine in self._engines.values():
            available, note = self.is_available(engine, settings)
            info = EngineInfo(
                id=engine.id,
                label=engine.label,
                description=engine.description,
                available=available,
                availability_note=note,
                model_id=engine.model_id,
            )
            if engine.id == "anthropic_claude":
                info.auth_method = settings.claude_auth_method
                info.model_id = settings.claude_model_id
                info.effort = settings.claude_effort
            elif engine.id == "openai_gpt":
                info.auth_method = settings.openai_gpt_auth_method
                info.model_id = settings.openai_gpt_model_id
                info.effort = settings.openai_gpt_effort
            infos.append(info)
        return infos

    async def run(
        self,
        engine_id: str,
        request: PARequest,
        scenario: dict,
        settings: Settings,
    ) -> tuple[Determination, str | None]:
        """Run the requested engine; on unavailability or failure fall back to the rules engine.

        Returns (determination, error_notice). The determination's attribution
        always reflects the engine that actually ran.
        """
        engine = self.get(engine_id)
        fallback = self._engines[self._fallback_id]

        if engine is not fallback:
            available, note = self.is_available(engine, settings)
            if not available:
                determination = await fallback.evaluate(request, scenario, settings)
                reason = note or "engine is not available"
                return determination, (
                    f"{engine.label} unavailable — fell back to the rules engine: {reason}"
                )
            try:
                determination = await engine.evaluate(request, scenario, settings)
                return determination, None
            except Exception as exc:  # noqa: BLE001 — any engine failure falls back
                reason = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
                determination = await fallback.evaluate(request, scenario, settings)
                return determination, (
                    f"{engine.label} unavailable — fell back to the rules engine: {reason}"
                )

        determination = await fallback.evaluate(request, scenario, settings)
        return determination, None
