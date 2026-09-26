"""Anthropic Claude engine: the vendored prior-auth-review skill through the CLI, API, or Bedrock."""

from ..config import Settings
from ..schemas import Determination, EngineId, PARequest
from .anthropic_api import call_anthropic_messages
from .base import Engine
from .bedrock import converse_with_bedrock
from .catalog import provider_model_id
from .claude_cli import run_claude_cli
from .llm_common import build_source_skill_prompt, determination_from_payload
from .provider_call import ProviderInvocation, invoke_and_parse


class AnthropicClaudeEngine(Engine):
    id: EngineId = "anthropic_claude"
    label = "Anthropic Claude"
    description = (
        "Claude applies the vendored prior-auth-review skill workflow and lenient "
        "approve/pend rubric."
    )

    async def evaluate(
        self,
        request: PARequest,
        scenario: dict,
        settings: Settings,
    ) -> Determination:
        prompt = build_source_skill_prompt(request, scenario)
        method = settings.claude_auth_method
        model_id = provider_model_id(self.id, settings.claude_model_id, method)
        effort = settings.claude_effort

        async def invoke() -> ProviderInvocation:
            if method == "cli":
                return await run_claude_cli(settings, prompt, model_id=model_id, effort=effort)
            if method == "api_key":
                return await call_anthropic_messages(settings, prompt, model_id=model_id, effort=effort)
            return await converse_with_bedrock(settings, prompt, model_id=model_id, effort=effort)

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
