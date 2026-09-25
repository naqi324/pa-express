"""Per-evaluation LLM trace capture for audit/sanity-check inspection."""

from contextvars import ContextVar, Token

from ..schemas import LlmTrace

_trace_buffer: ContextVar[list[LlmTrace] | None] = ContextVar(
    "pa_express_llm_trace_buffer", default=None
)


def begin_llm_trace_capture() -> Token[list[LlmTrace] | None]:
    return _trace_buffer.set([])


def record_llm_trace(trace: LlmTrace) -> None:
    buffer = _trace_buffer.get()
    if buffer is not None:
        buffer.append(trace)


def end_llm_trace_capture(token: Token[list[LlmTrace] | None]) -> list[LlmTrace]:
    buffer = _trace_buffer.get() or []
    _trace_buffer.reset(token)
    return buffer
