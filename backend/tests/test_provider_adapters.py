"""CLI and API adapter tests for the model-backed engines.

Every provider call is faked: CLIs through a stub subprocess, APIs through
httpx.MockTransport. No test reaches a real model.
"""

import asyncio
import json
from functools import partial

import httpx
import pytest

from backend.app.config import Settings
from backend.app.engines.anthropic_api import (
    anthropic_output_schema,
    build_anthropic_messages_request,
    call_anthropic_messages,
)
from backend.app.engines.anthropic_claude import AnthropicClaudeEngine
from backend.app.engines.base import EngineRegistry
from backend.app.engines.catalog import provider_model_id, resolve_effort
from backend.app.engines.claude_cli import build_claude_cli_args, claude_cli_result_text
from backend.app.engines.codex_cli import build_codex_args
from backend.app.engines.llm_common import llm_response_json_schema
from backend.app.engines.openai_api import build_openai_responses_request, call_openai_responses
from backend.app.engines.openai_gpt import OpenAiGptEngine
from backend.app.engines.provider_call import REDACTED, ProviderInvocationError
from backend.app.engines.rubric import RubricEngine
from backend.app.engines.trace import begin_llm_trace_capture, end_llm_trace_capture
from backend.app.errors import AppError
from backend.tests.test_rubric_and_registry import (
    MET_FACT,
    MET_FACT_2,
    make_request,
    make_scenario,
)

ANTHROPIC_KEY = "sk-ant-test-key-000000000000wxyz"
OPENAI_KEY = "sk-proj-test-key-00000000000abcd"

APPROVE_PAYLOAD = {
    "criteria": [
        {
            "criterion_id": "C1",
            "status": "MET",
            "evidence": [
                {
                    "quote": "Severe medial compartment narrowing on radiographs.",
                    "source_document": "Orthopedic Consult Note",
                    "document_date": "2026-06-20",
                }
            ],
            "rationale": "Supported.",
            "confidence": 90,
        },
        {
            "criterion_id": "C2",
            "status": "MET",
            "evidence": [
                {
                    "quote": "Completed 12 weeks of physical therapy and NSAIDs without relief.",
                    "source_document": "Orthopedic Consult Note",
                    "document_date": "2026-06-20",
                }
            ],
            "rationale": "Supported.",
            "confidence": 90,
        },
    ],
    "recommendation": "approve",
    "rationale": "All criteria met.",
}


def knee_case():
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    return make_request(scenario), scenario


def keys_in(node: object) -> set[str]:
    if isinstance(node, dict):
        found = set(node)
        for value in node.values():
            found |= keys_in(value)
        return found
    if isinstance(node, list):
        found: set[str] = set()
        for item in node:
            found |= keys_in(item)
        return found
    return set()


class FakeCliProcess:
    def __init__(self, captured: dict, *, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
        self._captured = captured
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self, input=None):
        self._captured["stdin"] = input
        return self._stdout, self._stderr


def fake_cli(monkeypatch: pytest.MonkeyPatch, captured: dict, **process_kwargs) -> None:
    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeCliProcess(captured, **process_kwargs)

    monkeypatch.setattr(
        "backend.app.engines.provider_call.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )


def route_api_calls(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Send both API adapters through a MockTransport for the engine under test."""
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "backend.app.engines.anthropic_claude.call_anthropic_messages",
        partial(call_anthropic_messages, transport=transport),
    )
    monkeypatch.setattr(
        "backend.app.engines.openai_gpt.call_openai_responses",
        partial(call_openai_responses, transport=transport),
    )


# Catalog


def test_catalog_resolves_defaults_and_rejects_unsupported_efforts() -> None:
    assert resolve_effort("anthropic_claude", "claude-opus-5-5", "cli", None) == "medium"
    assert resolve_effort("anthropic_claude", "claude-fable-5-1", "api_key", "max") == "max"
    # Claude Haiku 4.5 takes no effort, so any request resolves to None.
    assert resolve_effort("anthropic_claude", "claude-haiku-4-5-20251001", "bedrock", "high") is None
    assert resolve_effort("openai_gpt", "gpt-6-astra", "cli", "ultra") == "ultra"
    assert resolve_effort("openai_gpt", "gpt-6-sol", "api_key", "none") == "none"

    with pytest.raises(AppError) as ultra:
        resolve_effort("openai_gpt", "gpt-6-astra", "api_key", "ultra")
    assert ultra.value.code == "EFFORT_NOT_SUPPORTED"
    with pytest.raises(AppError) as astra_none:
        resolve_effort("openai_gpt", "gpt-6-astra", "api_key", "none")
    assert astra_none.value.code == "EFFORT_NOT_SUPPORTED"
    with pytest.raises(AppError) as unknown:
        resolve_effort("openai_gpt", "gpt-5.5", "cli", "high")
    assert unknown.value.code == "MODEL_NOT_SUPPORTED"


def test_settings_read_blank_efforts_as_the_model_default(monkeypatch) -> None:
    monkeypatch.setenv("PA_EXPRESS_CLAUDE_EFFORT", "")
    monkeypatch.setenv("PA_EXPRESS_OPENAI_GPT_MODEL_ID", "gpt-6-luna")
    monkeypatch.setenv("PA_EXPRESS_OPENAI_GPT_EFFORT", " ")
    settings = Settings()
    assert settings.claude_effort == "medium"
    assert settings.openai_gpt_effort == "medium"


def test_settings_read_host_lists_as_csv_or_json(monkeypatch) -> None:
    monkeypatch.setenv("PA_EXPRESS_ALLOWED_ORIGINS", "http://127.0.0.1:5175, http://localhost:5175")
    monkeypatch.setenv("PA_EXPRESS_TRUSTED_HOSTS", '["127.0.0.1", "localhost"]')
    settings = Settings()
    assert settings.allowed_origins == ["http://127.0.0.1:5175", "http://localhost:5175"]
    assert settings.trusted_hosts == ["127.0.0.1", "localhost"]


def test_catalog_maps_bedrock_to_inference_profiles() -> None:
    assert provider_model_id("anthropic_claude", "claude-opus-5-5", "cli") == "claude-opus-5-5"
    assert (
        provider_model_id("anthropic_claude", "claude-opus-5-5", "bedrock")
        == "us.anthropic.claude-opus-5-5"
    )
    assert (
        provider_model_id("anthropic_claude", "claude-haiku-4-5-20251001", "bedrock")
        == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )


# Claude Code CLI


def test_claude_cli_args_disable_customizations_and_tools() -> None:
    args = build_claude_cli_args(Settings(), model_id="claude-opus-5-5", effort="high")
    assert args[:2] == ["claude", "-p"]
    assert "--safe-mode" in args
    assert "--no-session-persistence" in args
    assert "--strict-mcp-config" in args
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--output-format") + 1] == "json"
    assert args[args.index("--model") + 1] == "claude-opus-5-5"
    assert args[args.index("--effort") + 1] == "high"

    haiku = build_claude_cli_args(Settings(), model_id="claude-haiku-4-5-20251001", effort=None)
    assert "--effort" not in haiku


def test_claude_cli_result_text_reads_every_envelope() -> None:
    payload = json.dumps(APPROVE_PAYLOAD)
    assert claude_cli_result_text(json.dumps({"type": "result", "result": payload})) == payload
    stream = [{"type": "system"}, {"type": "result", "result": payload}]
    assert claude_cli_result_text(json.dumps(stream)) == payload
    structured = {"type": "result", "result": "", "structured_output": APPROVE_PAYLOAD}
    assert json.loads(claude_cli_result_text(json.dumps(structured))) == APPROVE_PAYLOAD

    with pytest.raises(ValueError, match="reported an error"):
        claude_cli_result_text(json.dumps({"type": "result", "is_error": True, "result": "Not logged in"}))
    with pytest.raises(ValueError, match="empty result"):
        claude_cli_result_text(json.dumps({"type": "result", "result": "  "}))
    with pytest.raises(ValueError, match="no result message"):
        claude_cli_result_text(json.dumps([{"type": "system"}]))


async def test_claude_cli_engine_sends_prompt_on_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    request, scenario = knee_case()
    captured: dict = {}
    envelope = {"type": "result", "is_error": False, "result": json.dumps(APPROVE_PAYLOAD)}
    fake_cli(monkeypatch, captured, stdout=json.dumps(envelope).encode())

    token = begin_llm_trace_capture()
    determination = await AnthropicClaudeEngine().evaluate(
        request, scenario, Settings(mock_processing_seconds=0.0)
    )
    traces = end_llm_trace_capture(token)

    assert determination.recommendation == "approve"
    assert determination.attribution.model_id == "claude-opus-5-5"
    args = captured["args"]
    assert args[args.index("--model") + 1] == "claude-opus-5-5"
    assert args[args.index("--effort") + 1] == "high"
    assert captured["kwargs"]["stdin"] == asyncio.subprocess.PIPE
    prompt = captured["stdin"].decode("utf-8")
    assert "Total knee arthroplasty" in prompt
    # The case text is not an argument, so it never shows in the process list.
    assert all("Total knee arthroplasty" not in arg for arg in args)

    assert len(traces) == 1
    trace = traces[0]
    assert trace.status == "succeeded"
    assert trace.provider == "anthropic"
    assert trace.auth_method == "cli"
    assert trace.effort == "high"
    assert trace.request_payload["stdin"] == "<prompt>"


async def test_claude_cli_failure_records_a_failed_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    request, scenario = knee_case()
    captured: dict = {}
    fake_cli(monkeypatch, captured, stdout=b"", stderr=b"Not logged in. Run claude login.", returncode=1)

    token = begin_llm_trace_capture()
    with pytest.raises(ProviderInvocationError, match="exited with code 1: Not logged in"):
        await AnthropicClaudeEngine().evaluate(request, scenario, Settings(mock_processing_seconds=0.0))
    traces = end_llm_trace_capture(token)

    assert traces[0].status == "failed"
    assert traces[0].auth_method == "cli"
    assert "Not logged in" in traces[0].raw_response


# Codex CLI


def test_codex_args_read_the_prompt_from_stdin() -> None:
    args = build_codex_args(
        Settings(), model_id="gpt-6-luna", effort="low", schema_path="s.json", output_path="o.json"
    )
    assert args[-1] == "-"
    assert args[args.index("-m") + 1] == "gpt-6-luna"
    assert args[args.index("-c") + 1] == 'model_reasoning_effort="low"'

    no_effort = build_codex_args(
        Settings(), model_id="gpt-6-luna", effort=None, schema_path="s.json", output_path="o.json"
    )
    assert "-c" not in no_effort
    assert no_effort[-1] == "-"


# Claude API


def test_anthropic_request_uses_structured_output_and_adaptive_thinking() -> None:
    body = build_anthropic_messages_request(
        Settings(), "Review.", model_id="claude-fable-5-1", effort="xhigh"
    )
    assert body["model"] == "claude-fable-5-1"
    assert body["max_tokens"] == 16000
    assert body["messages"] == [{"role": "user", "content": "Review."}]
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"]["effort"] == "xhigh"
    assert body["output_config"]["format"]["type"] == "json_schema"
    # Claude structured outputs reject numeric bounds.
    schema = body["output_config"]["format"]["schema"]
    assert schema == anthropic_output_schema()
    assert not keys_in(schema) & {"minimum", "maximum"}
    assert keys_in(llm_response_json_schema()) & {"minimum", "maximum"}

    haiku = build_anthropic_messages_request(
        Settings(), "Review.", model_id="claude-haiku-4-5-20251001", effort=None
    )
    assert "thinking" not in haiku
    assert "effort" not in haiku["output_config"]


async def test_anthropic_api_engine_round_trip_keeps_the_key_out_of_traces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, scenario = knee_case()
    seen: dict = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["url"] = str(http_request.url)
        seen["headers"] = http_request.headers
        seen["body"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "", "signature": "sig"},
                    {"type": "text", "text": json.dumps(APPROVE_PAYLOAD)},
                ],
                "stop_reason": "end_turn",
            },
        )

    route_api_calls(monkeypatch, handler)
    settings = Settings(
        mock_processing_seconds=0.0,
        claude_auth_method="api_key",
        claude_model_id="claude-sonnet-5",
        claude_effort="medium",
        anthropic_api_key=ANTHROPIC_KEY,
    )

    token = begin_llm_trace_capture()
    determination = await AnthropicClaudeEngine().evaluate(request, scenario, settings)
    traces = end_llm_trace_capture(token)

    assert determination.recommendation == "approve"
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == ANTHROPIC_KEY
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["body"]["model"] == "claude-sonnet-5"
    assert seen["body"]["output_config"]["effort"] == "medium"

    trace = traces[0]
    assert trace.status == "succeeded"
    assert trace.provider == "anthropic"
    assert trace.auth_method == "api_key"
    assert trace.effort == "medium"
    assert ANTHROPIC_KEY not in trace.model_dump_json()


async def test_anthropic_api_errors_are_redacted() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "type": "error",
                "error": {"type": "authentication_error", "message": f"invalid x-api-key {ANTHROPIC_KEY}"},
            },
        )

    settings = Settings(anthropic_api_key=ANTHROPIC_KEY)
    with pytest.raises(ProviderInvocationError) as failure:
        await call_anthropic_messages(
            settings,
            "Review.",
            model_id="claude-opus-5-5",
            effort="high",
            transport=httpx.MockTransport(handler),
        )
    assert "returned 401" in str(failure.value)
    assert ANTHROPIC_KEY not in str(failure.value)
    assert REDACTED in str(failure.value)
    assert ANTHROPIC_KEY not in failure.value.invocation.raw_response


@pytest.mark.parametrize(
    ("stop_reason", "message"),
    [
        ("max_tokens", "reached the 16000-token limit"),
        ("refusal", "Claude declined to answer"),
    ],
)
async def test_anthropic_api_stop_reasons_fail_the_call(stop_reason: str, message: str) -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": "{"}], "stop_reason": stop_reason}
        )

    with pytest.raises(ProviderInvocationError, match=message):
        await call_anthropic_messages(
            Settings(anthropic_api_key=ANTHROPIC_KEY),
            "Review.",
            model_id="claude-opus-5-5",
            effort="high",
            transport=httpx.MockTransport(handler),
        )


# OpenAI API


def test_openai_request_uses_strict_schema_and_no_storage() -> None:
    body = build_openai_responses_request("Review.", model_id="gpt-6-sol", effort="none")
    assert body["model"] == "gpt-6-sol"
    assert body["input"] == "Review."
    assert body["store"] is False
    assert body["reasoning"] == {"effort": "none"}
    text_format = body["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["schema"] == llm_response_json_schema()

    no_effort = build_openai_responses_request("Review.", model_id="gpt-6-sol", effort=None)
    assert "reasoning" not in no_effort


async def test_openai_api_engine_round_trip_keeps_the_key_out_of_traces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request, scenario = knee_case()
    seen: dict = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["url"] = str(http_request.url)
        seen["headers"] = http_request.headers
        seen["body"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "status": "completed",
                "output": [
                    {"type": "reasoning", "summary": []},
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": json.dumps(APPROVE_PAYLOAD)}],
                    },
                ],
            },
        )

    route_api_calls(monkeypatch, handler)
    settings = Settings(
        mock_processing_seconds=0.0,
        openai_gpt_auth_method="api_key",
        openai_gpt_model_id="gpt-6-astra",
        openai_gpt_effort="xhigh",
        openai_api_key=OPENAI_KEY,
    )

    token = begin_llm_trace_capture()
    determination = await OpenAiGptEngine().evaluate(request, scenario, settings)
    traces = end_llm_trace_capture(token)

    assert determination.recommendation == "approve"
    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert seen["headers"]["authorization"] == f"Bearer {OPENAI_KEY}"
    assert seen["body"]["model"] == "gpt-6-astra"
    assert seen["body"]["reasoning"] == {"effort": "xhigh"}
    assert seen["body"]["store"] is False

    trace = traces[0]
    assert trace.status == "succeeded"
    assert trace.provider == "openai"
    assert trace.auth_method == "api_key"
    assert trace.effort == "xhigh"
    assert OPENAI_KEY not in trace.model_dump_json()


@pytest.mark.parametrize(
    ("response_json", "message"),
    [
        (
            {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": []},
            "incomplete: max_output_tokens",
        ),
        (
            {
                "status": "completed",
                "output": [
                    {"type": "message", "content": [{"type": "refusal", "refusal": "I can't help."}]}
                ],
            },
            "GPT declined to answer",
        ),
        (
            {"status": "failed", "error": {"message": "server overloaded"}, "output": []},
            "did not complete: server overloaded",
        ),
    ],
)
async def test_openai_api_unfinished_responses_fail_the_call(response_json: dict, message: str) -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_json)

    with pytest.raises(ProviderInvocationError, match=message):
        await call_openai_responses(
            Settings(openai_api_key=OPENAI_KEY),
            "Review.",
            model_id="gpt-6-sol",
            effort="medium",
            transport=httpx.MockTransport(handler),
        )


async def test_openai_api_errors_are_redacted() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"message": f"Incorrect API key provided: {OPENAI_KEY}."}}
        )

    with pytest.raises(ProviderInvocationError) as failure:
        await call_openai_responses(
            Settings(openai_api_key=OPENAI_KEY),
            "Review.",
            model_id="gpt-6-sol",
            effort="medium",
            transport=httpx.MockTransport(handler),
        )
    assert "returned 401" in str(failure.value)
    assert OPENAI_KEY not in str(failure.value)
    assert OPENAI_KEY not in failure.value.invocation.raw_response


# Fallback


async def test_registry_falls_back_when_an_api_call_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    request, scenario = knee_case()

    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"error": {"type": "overloaded_error", "message": "Overloaded"}})

    route_api_calls(monkeypatch, handler)
    registry = EngineRegistry({"offline": RubricEngine(), "anthropic_claude": AnthropicClaudeEngine()})
    settings = Settings(
        mock_processing_seconds=0.0,
        claude_auth_method="api_key",
        anthropic_api_key=ANTHROPIC_KEY,
    )

    token = begin_llm_trace_capture()
    determination, notice = await registry.run("anthropic_claude", request, scenario, settings)
    traces = end_llm_trace_capture(token)

    assert determination.attribution.engine == "offline"
    assert notice is not None
    assert "fell back to the rules engine: The Anthropic API returned 529: Overloaded" in notice
    assert traces[0].status == "failed"
    assert traces[0].auth_method == "api_key"
    assert ANTHROPIC_KEY not in traces[0].model_dump_json()
