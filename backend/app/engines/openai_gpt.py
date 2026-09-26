"""OpenAI GPT engine: the vendored skill as source material, through the Codex CLI or the API."""

from ..config import Settings
from ..schemas import Determination, EngineId, PARequest
from .base import Engine
from .catalog import provider_model_id
from .codex_cli import run_codex_cli
from .llm_common import build_openai_source_skill_prompt, determination_from_payload
from .openai_api import call_openai_responses
from .provider_call import ProviderInvocation, invoke_and_parse


class OpenAiGptEngine(Engine):
    id: EngineId = "openai_gpt"
    label = "OpenAI GPT"
    description = (
        "OpenAI GPT applies the vendored prior-auth-review skill prompt and lenient "
        "approve/pend rubric."
    )

    async def evaluate(
        self,
        request: PARequest,
        scenario: dict,
        settings: Settings,
    ) -> Determination:
        prompt = build_openai_source_skill_prompt(request, scenario)
        method = settings.openai_gpt_auth_method
        model_id = provider_model_id(self.id, settings.openai_gpt_model_id, method)
        effort = settings.openai_gpt_effort

        async def invoke() -> ProviderInvocation:
            if method == "api_key":
                return await call_openai_responses(settings, prompt, model_id=model_id, effort=effort)
            return await run_codex_cli(settings, prompt, model_id=model_id, effort=effort)

        payload, _ = await invoke_and_parse(
            engine=self.id, engine_label=self.label, prompt=prompt, invoke=invoke
        )
        return determination_from_payload(
            payload,
            request,
            scenario,
            engine=self.id,
            engine_label=self.label,
            model_id=model_id,
            require_all_criteria=True,
            enforce_recommendation=True,
            validate_evidence_quotes=True,
            require_evidence_for_met=True,
        )
