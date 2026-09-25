"""OpenAI GPT evaluation engine via the signed-in local Codex CLI."""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from ..schemas import Determination, EngineId, LlmTrace, PARequest
from .base import Engine
from .llm_common import (
    build_openai_source_skill_prompt,
    determination_from_payload,
    llm_response_json_schema,
    parse_llm_json,
)
from .trace import record_llm_trace


class CodexEngine(Engine):
    id: EngineId = "openai_gpt"
    label = "OpenAI GPT"
    description = (
        "OpenAI GPT through the signed-in local Codex CLI, applying the vendored "
        "prior-auth-review skill prompt."
    )
    model_id = None

    async def evaluate(
        self,
        request: PARequest,
        scenario: dict,
        settings: Settings,
    ) -> Determination:
        prompt = build_openai_source_skill_prompt(request, scenario)
        model_id = settings.codex_model_id.strip() or "gpt-5.5"
        with tempfile.TemporaryDirectory(prefix="pa-express-codex-") as temp_dir:
            run_dir = Path(temp_dir)
            schema_path = run_dir / "response-schema.json"
            output_path = run_dir / "final-message.json"
            schema_path.write_text(
                json.dumps(llm_response_json_schema(), separators=(",", ":")),
                encoding="utf-8",
            )
            args = [
                settings.codex_command,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-m",
                model_id,
                "-c",
                f'model_reasoning_effort="{settings.codex_effort}"',
                prompt,
            ]
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(run_dir),
            )
            stdout = b""
            stderr = b""
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=settings.engine_timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                _record_codex_trace(
                    settings=settings,
                    prompt=prompt,
                    args=args,
                    stdout=stdout,
                    stderr=stderr,
                    response_text=_read_codex_final_message(output_path, stdout),
                    status="failed",
                    error="Codex CLI timed out.",
                )
                raise

            response_text = _read_codex_final_message(output_path, stdout)
            if process.returncode != 0:
                detail = (stderr or b"").decode(errors="replace").strip()[:300]
                _record_codex_trace(
                    settings=settings,
                    prompt=prompt,
                    args=args,
                    stdout=stdout,
                    stderr=stderr,
                    response_text=response_text,
                    status="failed",
                    error=(
                        f"Codex CLI exited with code {process.returncode}: "
                        f"{detail or 'no stderr output'}"
                    ),
                )
                raise RuntimeError(
                    f"Codex CLI exited with code {process.returncode}: {detail or 'no stderr output'}"
                )

            try:
                payload = parse_llm_json(response_text)
            except Exception as exc:
                _record_codex_trace(
                    settings=settings,
                    prompt=prompt,
                    args=args,
                    stdout=stdout,
                    stderr=stderr,
                    response_text=response_text,
                    status="failed",
                    error=str(exc),
                )
                raise
            _record_codex_trace(
                settings=settings,
                prompt=prompt,
                args=args,
                stdout=stdout,
                stderr=stderr,
                response_text=response_text,
                status="succeeded",
                parsed_response=payload,
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


def _record_codex_trace(
    *,
    settings: Settings,
    prompt: str,
    args: list[str],
    stdout: bytes,
    stderr: bytes,
    response_text: str,
    status: str,
    parsed_response: dict | None = None,
    error: str | None = None,
) -> None:
    raw_stdout = (stdout or b"").decode(errors="replace")
    raw_stderr = (stderr or b"").decode(errors="replace")
    display_args = _sanitize_codex_args(args)
    record_llm_trace(
        LlmTrace(
            provider="openai",
            engine=CodexEngine.id,
            engine_label=CodexEngine.label,
            model_id=settings.codex_model_id.strip() or "gpt-5.5",
            created_at=datetime.now(timezone.utc).isoformat(),
            status=status,  # type: ignore[arg-type]
            prompt=prompt,
            request_payload={
                "argv": display_args,
                "runner": "codex_cli",
                "uses_codex_user_config": True,
                "cwd": "<temporary evaluation workspace>",
                "output_schema": llm_response_json_schema(),
                "model": settings.codex_model_id.strip() or "gpt-5.5",
                "reasoning_effort": settings.codex_effort,
            },
            raw_response=(
                "FINAL MESSAGE:\n"
                f"{response_text}\n\nSTDOUT:\n{raw_stdout}\n\nSTDERR:\n{raw_stderr}"
                if raw_stderr
                else f"FINAL MESSAGE:\n{response_text}\n\nSTDOUT:\n{raw_stdout}"
            ),
            response_text=response_text,
            parsed_response=parsed_response,
            error=error,
            redactions=[
                "Codex auth tokens and OpenAI account details stay inside the local Codex CLI config."
            ],
        )
    )


def _read_codex_final_message(output_path: Path, stdout: bytes) -> str:
    try:
        final_message = output_path.read_text(encoding="utf-8").strip()
    except OSError:
        final_message = ""
    if final_message:
        return final_message
    return (stdout or b"").decode(errors="replace")


def _sanitize_codex_args(args: list[str]) -> list[str]:
    display_args = list(args)
    for index, value in enumerate(display_args):
        if value == "--output-schema" and index + 1 < len(display_args):
            display_args[index + 1] = "<response-schema.json>"
        if value in {"--output-last-message", "-o"} and index + 1 < len(display_args):
            display_args[index + 1] = "<final-message.json>"
    if display_args:
        display_args[-1] = "<prompt>"
    return display_args
