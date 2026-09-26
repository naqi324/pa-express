"""AWS Bedrock adapter for the Anthropic Claude engine."""

import asyncio
import json
from typing import Any

from ..config import Settings
from ..schemas import ReasoningEffort
from .provider_call import ProviderInvocation, ProviderInvocationError


def build_bedrock_converse_request(
    settings: Settings, prompt: str, *, model_id: str, effort: ReasoningEffort | None
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": settings.claude_max_tokens},
    }
    # Models with an effort setting run adaptive thinking. Claude Haiku 4.5 takes neither.
    if effort is not None:
        request["additionalModelRequestFields"] = {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }
    return request


def _response_text(response: dict[str, Any]) -> str:
    blocks = response["output"]["message"]["content"]
    return "".join(block.get("text", "") for block in blocks)


def invoke_bedrock_converse(
    settings: Settings, prompt: str, *, model_id: str, effort: ReasoningEffort | None
) -> ProviderInvocation:
    import boto3

    request_payload = build_bedrock_converse_request(settings, prompt, model_id=model_id, effort=effort)
    invocation = ProviderInvocation(
        provider="bedrock",
        auth_method="bedrock",
        model_id=model_id,
        effort=effort,
        request_payload=request_payload,
        redactions=["AWS credentials are never included in the Bedrock request payload."],
    )
    if settings.bedrock_credentials == "access_keys" and settings.aws_access_key_id:
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
        raise ProviderInvocationError(
            f"Bedrock Converse request failed: {exc}", invocation
        ) from exc
    invocation.raw_response = json.dumps(response, indent=2, sort_keys=True, default=str)
    invocation.response_text = _response_text(response)
    return invocation


async def converse_with_bedrock(
    settings: Settings, prompt: str, *, model_id: str, effort: ReasoningEffort | None
) -> ProviderInvocation:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(invoke_bedrock_converse, settings, prompt, model_id=model_id, effort=effort),
            timeout=settings.engine_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        invocation = ProviderInvocation(
            provider="bedrock",
            auth_method="bedrock",
            model_id=model_id,
            effort=effort,
            request_payload=build_bedrock_converse_request(
                settings, prompt, model_id=model_id, effort=effort
            ),
        )
        raise ProviderInvocationError("Bedrock Converse request timed out.", invocation) from exc
