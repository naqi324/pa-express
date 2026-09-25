"""Anthropic Claude engine via Bedrock using the vendored prior-auth-review skill."""

from ..config import Settings
from ..schemas import Determination, EngineId, PARequest
from .base import Engine
from .bedrock import BedrockInvocation, BedrockInvocationError, _record_bedrock_trace, converse_with_bedrock
from .llm_common import (
    build_source_skill_prompt,
    determination_from_payload,
    parse_llm_json,
)


class AnthropicClaudeEngine(Engine):
    id: EngineId = "anthropic_claude"
    label = "Anthropic Claude"
    description = (
        "Claude on Bedrock applies the vendored prior-auth-review skill workflow and "
        "lenient approve/pend rubric."
    )

    async def evaluate(
        self,
        request: PARequest,
        scenario: dict,
        settings: Settings,
    ) -> Determination:
        prompt = build_source_skill_prompt(request, scenario)
        invocation: BedrockInvocation | None = None
        try:
            invocation = await converse_with_bedrock(settings, prompt)
            payload = parse_llm_json(invocation.response_text)
        except BedrockInvocationError as exc:
            _record_bedrock_trace(
                engine=self.id,
                engine_label=self.label,
                settings=settings,
                prompt=prompt,
                invocation=exc.invocation,
                status="failed",
                error=str(exc.__cause__ or exc),
            )
            raise
        except Exception as exc:
            if invocation is not None:
                _record_bedrock_trace(
                    engine=self.id,
                    engine_label=self.label,
                    settings=settings,
                    prompt=prompt,
                    invocation=invocation,
                    status="failed",
                    error=str(exc),
                )
            raise
        _record_bedrock_trace(
            engine=self.id,
            engine_label=self.label,
            settings=settings,
            prompt=prompt,
            invocation=invocation,
            status="succeeded",
            parsed_response=payload,
        )
        return determination_from_payload(
            payload,
            request,
            scenario,
            engine=self.id,
            engine_label=self.label,
            model_id=settings.bedrock_model_id,
            require_all_criteria=True,
            enforce_recommendation=True,
            validate_evidence_quotes=True,
            require_evidence_for_met=True,
        )
