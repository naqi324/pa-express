"""OpenAI API adapter: one Responses API call with a session API key."""

import asyncio
import json
from typing import Any

import httpx

from ..config import Settings
from ..schemas import ReasoningEffort
from .llm_common import llm_response_json_schema
from .provider_call import ProviderInvocation, ProviderInvocationError, redact

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def build_openai_responses_request(
    prompt: str, *, model_id: str, effort: ReasoningEffort | None
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model_id,
        "input": prompt,
        # Case text is PHI: ask OpenAI not to keep the response for later retrieval.
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "prior_auth_determination",
                "schema": llm_response_json_schema(),
                "strict": True,
            }
        },
    }
    if effort is not None:
        body["reasoning"] = {"effort": effort}
    return body


async def call_openai_responses(
    settings: Settings,
    prompt: str,
    *,
    model_id: str,
    effort: ReasoningEffort | None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ProviderInvocation:
    api_key = settings.openai_api_key.get_secret_value()
    body = build_openai_responses_request(prompt, model_id=model_id, effort=effort)
    invocation = ProviderInvocation(
        provider="openai",
        auth_method="api_key",
        model_id=model_id,
        effort=effort,
        request_payload={
            "url": OPENAI_RESPONSES_URL,
            "headers": {"content-type": "application/json"},
            "body": body,
        },
        redactions=["The OpenAI API key is sent as a bearer token and never recorded."],
    )
    headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
    try:
        async with httpx.AsyncClient(transport=transport, timeout=settings.engine_timeout_seconds) as client:
            response = await asyncio.wait_for(
                client.post(OPENAI_RESPONSES_URL, headers=headers, json=body),
                timeout=settings.engine_timeout_seconds,
            )
    except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
        raise ProviderInvocationError("The OpenAI API timed out.", invocation) from exc
    except httpx.HTTPError as exc:
        message = redact(f"The OpenAI API request failed: {exc}", [api_key])
        raise ProviderInvocationError(message, invocation) from exc
    # OpenAI echoes part of a rejected key in 401 errors; redact before recording.
    invocation.raw_response = redact(response.text, [api_key])
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code != 200:
        detail = redact(_error_message(data) or response.reason_phrase, [api_key])
        raise ProviderInvocationError(
            f"The OpenAI API returned {response.status_code}: {detail}", invocation
        )
    invocation.raw_response = json.dumps(data, indent=2, sort_keys=True)
    text_parts: list[str] = []
    for item in data.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "output_text":
                text_parts.append(part.get("text", ""))
            elif part.get("type") == "refusal":
                invocation.response_text = str(part.get("refusal", ""))
                raise ProviderInvocationError("GPT declined to answer this request.", invocation)
    invocation.response_text = "".join(text_parts)
    status = data.get("status")
    if status == "incomplete":
        reason = (data.get("incomplete_details") or {}).get("reason") or "unknown reason"
        raise ProviderInvocationError(f"The OpenAI response was incomplete: {reason}.", invocation)
    if status not in (None, "completed"):
        detail = _error_message(data) or f"status {status}"
        raise ProviderInvocationError(f"The OpenAI response did not complete: {detail}.", invocation)
    return invocation


def _error_message(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        return str(data["error"].get("message") or "")
    return ""
