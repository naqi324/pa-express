"""Codex CLI adapter: one `codex exec` run per evaluation."""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from ..config import Settings
from ..schemas import ReasoningEffort
from .llm_common import llm_response_json_schema
from .provider_call import (
    ProviderInvocation,
    ProviderInvocationError,
    cli_error_detail,
    cli_raw_response,
    run_cli_process,
)


def build_codex_args(
    settings: Settings,
    *,
    model_id: str,
    effort: ReasoningEffort | None,
    schema_path: str,
    output_path: str,
) -> list[str]:
    args = [
        settings.codex_command,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--output-schema",
        schema_path,
        "--output-last-message",
        output_path,
        "-m",
        model_id,
    ]
    if effort is not None:
        args += ["-c", f'model_reasoning_effort="{effort}"']
    # "-" reads the prompt from stdin, so case text stays out of the process list.
    args.append("-")
    return args


async def run_codex_cli(
    settings: Settings, prompt: str, *, model_id: str, effort: ReasoningEffort | None
) -> ProviderInvocation:
    with tempfile.TemporaryDirectory(prefix="pa-express-codex-") as temp_dir:
        run_dir = Path(temp_dir)
        schema_path = run_dir / "response-schema.json"
        output_path = run_dir / "final-message.json"
        schema_path.write_text(
            json.dumps(llm_response_json_schema(), separators=(",", ":")),
            encoding="utf-8",
        )
        args = build_codex_args(
            settings,
            model_id=model_id,
            effort=effort,
            schema_path=str(schema_path),
            output_path=str(output_path),
        )
        request_payload: dict[str, Any] = {
            "runner": "codex_cli",
            "argv": _display_args(args),
            "stdin": "<prompt>",
            "uses_codex_user_config": True,
            "cwd": "<temporary evaluation workspace>",
            "output_schema": llm_response_json_schema(),
            "model": model_id,
            "reasoning_effort": effort,
        }
        invocation = ProviderInvocation(
            provider="openai",
            auth_method="cli",
            model_id=model_id,
            effort=effort,
            request_payload=request_payload,
            redactions=[
                "Codex auth tokens and OpenAI account details stay inside the local Codex CLI config."
            ],
        )
        try:
            result = await run_cli_process(
                args, stdin_text=prompt, cwd=str(run_dir), timeout=settings.engine_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            invocation.response_text = _read_final_message(output_path, b"")
            raise ProviderInvocationError("Codex CLI timed out.", invocation) from exc
        except OSError as exc:
            raise ProviderInvocationError(f"Codex CLI could not start: {exc}", invocation) from exc
        invocation.response_text = _read_final_message(output_path, result.stdout)
    invocation.raw_response = cli_raw_response(invocation.response_text, result)
    if result.returncode != 0:
        raise ProviderInvocationError(
            f"Codex CLI exited with code {result.returncode}: {cli_error_detail(result)}",
            invocation,
        )
    return invocation


def _read_final_message(output_path: Path, stdout: bytes) -> str:
    try:
        final_message = output_path.read_text(encoding="utf-8").strip()
    except OSError:
        final_message = ""
    if final_message:
        return final_message
    return stdout.decode(errors="replace")


def _display_args(args: list[str]) -> list[str]:
    display_args = list(args)
    for index, value in enumerate(display_args[:-1]):
        if value == "--output-schema":
            display_args[index + 1] = "<response-schema.json>"
        if value == "--output-last-message":
            display_args[index + 1] = "<final-message.json>"
    return display_args
