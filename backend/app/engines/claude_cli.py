"""Claude Code CLI adapter: one headless `claude -p` run per evaluation."""

import asyncio
import json
import tempfile
from typing import Any

from ..config import Settings
from ..schemas import ReasoningEffort
from .provider_call import (
    CliResult,
    ProviderInvocation,
    ProviderInvocationError,
    cli_error_detail,
    cli_raw_response,
    run_cli_process,
)


def build_claude_cli_args(settings: Settings, *, model_id: str, effort: ReasoningEffort | None) -> list[str]:
    # --safe-mode skips the operator's CLAUDE.md, hooks, plugins, and MCP servers.
    # --tools "" removes every built-in tool; the prompt goes on stdin.
    args = [
        settings.claude_command,
        "-p",
        "--safe-mode",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--tools",
        "",
        "--model",
        model_id,
    ]
    if effort is not None:
        args += ["--effort", effort]
    return args


def claude_cli_result_text(stdout: str) -> str:
    """Return the final answer from `--output-format json`, or raise ValueError."""
    envelope = json.loads(stdout)
    if isinstance(envelope, list):
        results = [item for item in envelope if isinstance(item, dict) and item.get("type") == "result"]
        if not results:
            raise ValueError("Claude Code CLI output had no result message.")
        envelope = results[-1]
    if not isinstance(envelope, dict):
        raise ValueError("Claude Code CLI output was not a JSON object.")
    if envelope.get("is_error"):
        detail = str(envelope.get("result") or envelope.get("subtype") or "unknown error")[:300]
        raise ValueError(f"Claude Code CLI reported an error: {detail}")
    structured = envelope.get("structured_output")
    if isinstance(structured, dict):
        return json.dumps(structured)
    result = envelope.get("result")
    if not isinstance(result, str) or not result.strip():
        raise ValueError("Claude Code CLI returned an empty result.")
    return result


async def run_claude_cli(
    settings: Settings, prompt: str, *, model_id: str, effort: ReasoningEffort | None
) -> ProviderInvocation:
    args = build_claude_cli_args(settings, model_id=model_id, effort=effort)
    request_payload: dict[str, Any] = {
        "runner": "claude_cli",
        "argv": args,
        "stdin": "<prompt>",
        "cwd": "<temporary evaluation workspace>",
        "model": model_id,
        "effort": effort,
    }
    invocation = ProviderInvocation(
        provider="anthropic",
        auth_method="cli",
        model_id=model_id,
        effort=effort,
        request_payload=request_payload,
        redactions=["Claude Code sign-in details stay inside the local CLI config."],
    )
    with tempfile.TemporaryDirectory(prefix="pa-express-claude-") as run_dir:
        try:
            result = await run_cli_process(
                args, stdin_text=prompt, cwd=run_dir, timeout=settings.engine_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise ProviderInvocationError("Claude Code CLI timed out.", invocation) from exc
        except OSError as exc:
            raise ProviderInvocationError(f"Claude Code CLI could not start: {exc}", invocation) from exc
    return _finish(invocation, result)


def _finish(invocation: ProviderInvocation, result: CliResult) -> ProviderInvocation:
    stdout = result.stdout.decode(errors="replace")
    invocation.raw_response = cli_raw_response("", result)
    if result.returncode != 0:
        raise ProviderInvocationError(
            f"Claude Code CLI exited with code {result.returncode}: {cli_error_detail(result)}",
            invocation,
        )
    try:
        invocation.response_text = claude_cli_result_text(stdout)
    except ValueError as exc:
        raise ProviderInvocationError(str(exc), invocation) from exc
    invocation.raw_response = cli_raw_response(invocation.response_text, result)
    return invocation
