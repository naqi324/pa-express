"""Claude API adapter: one Messages API call with a session API key."""

import asyncio
import json
from typing import Any

import httpx

from ..config import Settings
from ..schemas import ReasoningEffort
from .llm_common import llm_response_json_schema
from .provider_call import ProviderInvocation, ProviderInvocationError, redact

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Claude structured outputs reject numeric bounds; confidence is clamped after parsing.
_UNSUPPORTED_SCHEMA_KEYS = {"minimum", "maximum"}


def anthropic_output_schema() -> dict[str, Any]:
    return _without_keys(llm_response_json_schema(), _UNSUPPORTED_SCHEMA_KEYS)


def _without_keys(node: Any, keys: set[str]) -> Any:
    if isinstance(node, dict):
        return {key: _without_keys(value, keys) for key, value in node.items() if key not in keys}
    if isinstance(node, list):
        return [_without_keys(item, keys) for item in node]
    return node


def build_anthropic_messages_request(
    settings: Settings, prompt: str, *, model_id: str, effort: ReasoningEffort | None
) -> dict[str, Any]:
    output_config: dict[str, Any] = {
        "format": {"type": "json_schema", "schema": anthropic_output_schema()}
    }
    body: dict[str, Any] = {
        "model": model_id,
        "max_tokens": settings.claude_max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": output_config,
    }
    # Models with an effort setting run adaptive thinking. Claude Haiku 4.5 takes neither.
    if effort is not None:
        body["thinking"] = {"type": "adaptive"}
        output_config["effort"] = effort
    return body


async def call_anthropic_messages(
    settings: Settings,
    prompt: str,
    *,
    model_id: str,
    effort: ReasoningEffort | None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ProviderInvocation:
    api_key = settings.anthropic_api_key.get_secret_value()
    body = build_anthropic_messages_request(settings, prompt, model_id=model_id, effort=effort)
    invocation = ProviderInvocation(
        provider="anthropic",
        auth_method="api_key",
        model_id=model_id,
        effort=effort,
        request_payload={
            "url": ANTHROPIC_MESSAGES_URL,
            "headers": {"anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"},
            "body": body,
        },
        redactions=["The Anthropic API key is sent in the x-api-key header and never recorded."],
    )
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(transport=transport, timeout=settings.engine_timeout_seconds) as client:
            response = await asyncio.wait_for(
                client.post(ANTHROPIC_MESSAGES_URL, headers=headers, json=body),
                timeout=settings.engine_timeout_seconds,
            )
    except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
        raise ProviderInvocationError("The Anthropic API timed out.", invocation) from exc
    except httpx.HTTPError as exc:
        message = redact(f"The Anthropic API request failed: {exc}", [api_key])
        raise ProviderInvocationError(message, invocation) from exc
    invocation.raw_response = redact(response.text, [api_key])
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code != 200:
        detail = redact(_error_message(data) or response.reason_phrase, [api_key])
        raise ProviderInvocationError(
            f"The Anthropic API returned {response.status_code}: {detail}", invocation
        )
    invocation.raw_response = json.dumps(data, indent=2, sort_keys=True)
    invocation.response_text = "".join(
        block.get("text", "") for block in data.get("content") or [] if block.get("type") == "text"
    )
    stop_reason = data.get("stop_reason")
    if stop_reason == "max_tokens":
        raise ProviderInvocationError(
            f"The response reached the {settings.claude_max_tokens}-token limit before it finished.",
            invocation,
        )
    if stop_reason == "refusal":
        raise ProviderInvocationError("Claude declined to answer this request.", invocation)
    return invocation


def _error_message(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        return str(data["error"].get("message") or "")
    return ""
