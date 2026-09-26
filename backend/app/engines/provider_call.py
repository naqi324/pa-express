"""Shared plumbing for provider calls: invocation records, CLI processes, and traces."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from ..schemas import AuthMethod, EngineId, LlmProvider, LlmTrace, ReasoningEffort
from .llm_common import parse_llm_json
from .trace import record_llm_trace

REDACTED = "<redacted>"


@dataclass
class ProviderInvocation:
    """What one provider call sent and received, as the inspector shows it."""

    provider: LlmProvider
    auth_method: AuthMethod
    model_id: str
    effort: ReasoningEffort | None
    request_payload: dict[str, Any]
    raw_response: str = ""
    response_text: str = ""
    redactions: list[str] = field(default_factory=list)


class ProviderInvocationError(RuntimeError):
    def __init__(self, message: str, invocation: ProviderInvocation) -> None:
        super().__init__(message)
        self.invocation = invocation


@dataclass
class CliResult:
    stdout: bytes
    stderr: bytes
    returncode: int


def redact(text: str, secrets: list[str]) -> str:
    """Replace each non-empty secret in text. Provider errors can echo request data."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return text


def cli_raw_response(response_text: str, result: CliResult) -> str:
    stdout = result.stdout.decode(errors="replace")
    stderr = result.stderr.decode(errors="replace")
    raw = f"FINAL MESSAGE:\n{response_text}\n\nSTDOUT:\n{stdout}"
    if stderr:
        raw += f"\n\nSTDERR:\n{stderr}"
    return raw


def cli_error_detail(result: CliResult) -> str:
    detail = result.stderr.decode(errors="replace").strip()[:300]
    return detail or "no stderr output"


async def run_cli_process(
    args: list[str], *, stdin_text: str, cwd: str, timeout: float
) -> CliResult:
    """Run a CLI with the prompt on stdin, so case text stays out of the process list."""
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(stdin_text.encode("utf-8")), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise
    return CliResult(stdout=stdout or b"", stderr=stderr or b"", returncode=process.returncode or 0)


def record_invocation_trace(
    *,
    engine: EngineId,
    engine_label: str,
    prompt: str,
    invocation: ProviderInvocation,
    status: Literal["succeeded", "failed"],
    parsed_response: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    record_llm_trace(
        LlmTrace(
            provider=invocation.provider,
            engine=engine,
            engine_label=engine_label,
            auth_method=invocation.auth_method,
            model_id=invocation.model_id,
            effort=invocation.effort,
            created_at=datetime.now(timezone.utc).isoformat(),
            status=status,
            prompt=prompt,
            request_payload=invocation.request_payload,
            raw_response=invocation.raw_response,
            response_text=invocation.response_text,
            parsed_response=parsed_response,
            error=error,
            redactions=invocation.redactions,
        )
    )


async def invoke_and_parse(
    *,
    engine: EngineId,
    engine_label: str,
    prompt: str,
    invoke: Callable[[], Awaitable[ProviderInvocation]],
) -> tuple[dict[str, Any], ProviderInvocation]:
    """Run one provider call, parse its JSON, and record a trace either way."""
    invocation: ProviderInvocation | None = None
    try:
        invocation = await invoke()
        payload = parse_llm_json(invocation.response_text)
    except ProviderInvocationError as exc:
        record_invocation_trace(
            engine=engine,
            engine_label=engine_label,
            prompt=prompt,
            invocation=exc.invocation,
            status="failed",
            error=str(exc),
        )
        raise
    except Exception as exc:
        if invocation is not None:
            record_invocation_trace(
                engine=engine,
                engine_label=engine_label,
                prompt=prompt,
                invocation=invocation,
                status="failed",
                error=str(exc),
            )
        raise
    record_invocation_trace(
        engine=engine,
        engine_label=engine_label,
        prompt=prompt,
        invocation=invocation,
        status="succeeded",
        parsed_response=payload,
    )
    return payload, invocation
