"""Engine abstraction + registry with cheap availability checks and Offline fallback."""

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
    label = "Offline"
    description = (
        "No-network execution of the vendored prior-auth-review skill's lenient rubric."
    )


def _bedrock_availability(settings: Settings) -> tuple[bool, str]:
    if not settings.bedrock_enabled:
        return False, "Anthropic Claude is disabled for this deployment."
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False, "boto3 is not installed in this environment."
    if settings.bedrock_auth_method == "access_keys":
        if not (settings.aws_access_key_id and settings.aws_secret_access_key):
            return False, "AWS access keys are selected but not yet entered for this session."
        return True, f"Uses session AWS access keys in {settings.bedrock_region}"
    if settings.aws_profile:
        return True, f"Uses AWS profile {settings.aws_profile} in {settings.bedrock_region}"
    return True, f"Uses the default AWS credential chain in {settings.bedrock_region}"


def _codex_availability(settings: Settings) -> tuple[bool, str]:
    if not settings.codex_enabled:
        return False, "OpenAI GPT is disabled for this deployment."
    if shutil.which(settings.codex_command) is None:
        return False, f"The '{settings.codex_command}' CLI was not found on PATH."
    return True, f"Runs OpenAI GPT through the local '{settings.codex_command}' CLI."


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
            return _bedrock_availability(settings)
        if engine.id == "openai_gpt":
            return _codex_availability(settings)
        return engine.availability(settings)

    def list_engines(self, settings: Settings) -> list[EngineInfo]:
        infos: list[EngineInfo] = []
        for engine in self._engines.values():
            available, note = self.is_available(engine, settings)
            model_id = engine.model_id
            if engine.id == "anthropic_claude":
                model_id = settings.bedrock_model_id
            elif engine.id == "openai_gpt":
                model_id = settings.codex_model_id or None
            infos.append(
                EngineInfo(
                    id=engine.id,
                    label=engine.label,
                    description=engine.description,
                    available=available,
                    availability_note=note,
                    model_id=model_id,
                )
            )
        return infos

    async def run(
        self,
        engine_id: str,
        request: PARequest,
        scenario: dict,
        settings: Settings,
    ) -> tuple[Determination, str | None]:
        """Run the requested engine; on unavailability or failure fall back to Offline.

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
                    f"{engine.label} unavailable — fell back to Offline: {reason}"
                )
            try:
                determination = await engine.evaluate(request, scenario, settings)
                return determination, None
            except Exception as exc:  # noqa: BLE001 — any engine failure falls back
                reason = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
                determination = await fallback.evaluate(request, scenario, settings)
                return determination, (
                    f"{engine.label} unavailable — fell back to Offline: {reason}"
                )

        determination = await fallback.evaluate(request, scenario, settings)
        return determination, None
