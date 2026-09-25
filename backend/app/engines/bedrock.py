"""AWS Bedrock provider helpers for the Anthropic Claude engine."""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..config import Settings
from ..schemas import EngineId, LlmTrace
from .trace import record_llm_trace


@dataclass
class BedrockInvocation:
    request_payload: dict[str, Any]
    raw_response: str = ""
    response_text: str = ""


class BedrockInvocationError(RuntimeError):
    def __init__(self, message: str, invocation: BedrockInvocation) -> None:
        super().__init__(message)
        self.invocation = invocation


def build_bedrock_converse_request(settings: Settings, prompt: str) -> dict[str, Any]:
    return {
        "modelId": settings.bedrock_model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": settings.bedrock_max_tokens},
        "additionalModelRequestFields": {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": settings.bedrock_effort},
        },
    }


def _json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=str)


def _response_text(response: dict[str, Any]) -> str:
    blocks = response["output"]["message"]["content"]
    return "".join(block.get("text", "") for block in blocks)


def _record_bedrock_trace(
    *,
    engine: EngineId,
    engine_label: str,
    settings: Settings,
    prompt: str,
    invocation: BedrockInvocation,
    status: str,
    parsed_response: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    record_llm_trace(
        LlmTrace(
            provider="bedrock",
            engine=engine,
            engine_label=engine_label,
            model_id=settings.bedrock_model_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            status=status,  # type: ignore[arg-type]
            prompt=prompt,
            request_payload=invocation.request_payload,
            raw_response=invocation.raw_response,
            response_text=invocation.response_text,
            parsed_response=parsed_response,
            error=error,
            redactions=["AWS credentials are never included in the Bedrock request payload."],
        )
    )


def invoke_bedrock_converse(settings: Settings, prompt: str) -> BedrockInvocation:
    import boto3

    request_payload = build_bedrock_converse_request(settings, prompt)
    invocation = BedrockInvocation(request_payload=request_payload)
    if settings.bedrock_auth_method == "access_keys" and settings.aws_access_key_id:
        session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_session_token=settings.aws_session_token or None,
        )
    elif settings.aws_profile:
        session = boto3.Session(profile_name=settings.aws_profile)
    else:
        # No named profile: use the standard boto3 credential chain.
        session = boto3.Session()
    client = session.client("bedrock-runtime", region_name=settings.bedrock_region)
    try:
        response = client.converse(**request_payload)
    except Exception as exc:  # noqa: BLE001 - preserve request payload for inspector
        raise BedrockInvocationError(
            f"Bedrock Converse request failed: {exc}", invocation
        ) from exc
    invocation.raw_response = _json_dumps(response)
    invocation.response_text = _response_text(response)
    return invocation


async def converse_with_bedrock(settings: Settings, prompt: str) -> BedrockInvocation:
    return await asyncio.wait_for(
        asyncio.to_thread(invoke_bedrock_converse, settings, prompt),
        timeout=settings.engine_timeout_seconds,
    )
