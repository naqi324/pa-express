"""Model catalog for the model-backed engines: auth methods, models, and efforts.

The API returns this catalog, the settings form renders from it, and the server
validates every saved choice against it.

Sources, checked 2026-09-25:
- Claude models and effort: https://platform.claude.com/docs/en/models/overview and
  https://platform.claude.com/docs/en/build-with-claude/effort
- Claude Code CLI: local `claude --help` (2.1.283); `--effort low|medium|high|xhigh|max`.
- OpenAI models and reasoning: https://developers.openai.com/api/docs/models and
  https://developers.openai.com/api/docs/guides/reasoning
- Codex CLI: the local Codex model cache (codex-cli 0.157.0).
"""

from ..errors import AppError
from ..schemas import (
    AuthMethod,
    AuthMethodOption,
    ModelMethodSupport,
    ModelOption,
    ReasoningEffort,
)

_CLAUDE_EFFORTS: list[ReasoningEffort] = ["low", "medium", "high", "xhigh", "max"]
_CODEX_EFFORTS: list[ReasoningEffort] = ["low", "medium", "high", "xhigh", "max", "ultra"]
_CODEX_EFFORTS_NO_ULTRA: list[ReasoningEffort] = ["low", "medium", "high", "xhigh", "max"]
_OPENAI_API_EFFORTS: list[ReasoningEffort] = ["none", "low", "medium", "high", "xhigh", "max"]
_OPENAI_API_EFFORTS_NO_NONE: list[ReasoningEffort] = ["low", "medium", "high", "xhigh", "max"]


def _claude_model(
    model_id: str,
    label: str,
    summary: str,
    *,
    bedrock_id: str,
    default_effort: ReasoningEffort | None,
) -> ModelOption:
    efforts = _CLAUDE_EFFORTS if default_effort is not None else []
    return ModelOption(
        id=model_id,
        label=label,
        summary=summary,
        methods=[
            ModelMethodSupport(
                auth_method="cli",
                provider_model_id=model_id,
                efforts=efforts,
                default_effort=default_effort,
            ),
            ModelMethodSupport(
                auth_method="api_key",
                provider_model_id=model_id,
                efforts=efforts,
                default_effort=default_effort,
            ),
            ModelMethodSupport(
                auth_method="bedrock",
                provider_model_id=bedrock_id,
                efforts=efforts,
                default_effort=default_effort,
            ),
        ],
    )


def _gpt_model(
    model_id: str,
    label: str,
    summary: str,
    *,
    codex_efforts: list[ReasoningEffort],
    api_efforts: list[ReasoningEffort],
) -> ModelOption:
    return ModelOption(
        id=model_id,
        label=label,
        summary=summary,
        methods=[
            ModelMethodSupport(
                auth_method="cli",
                provider_model_id=model_id,
                efforts=codex_efforts,
                default_effort="medium",
            ),
            ModelMethodSupport(
                auth_method="api_key",
                provider_model_id=model_id,
                efforts=api_efforts,
                default_effort="medium",
            ),
        ],
    )


CLAUDE_MODELS: list[ModelOption] = [
    _claude_model(
        "claude-opus-5-5",
        "Claude Opus 5.5",
        "For long-running agentic coding and knowledge work. Moderate latency.",
        bedrock_id="us.anthropic.claude-opus-5-5",
        default_effort="medium",
    ),
    _claude_model(
        "claude-fable-5-1",
        "Claude Fable 5.1",
        "For demanding reasoning and long-horizon agentic work. Slower.",
        bedrock_id="us.anthropic.claude-fable-5-1",
        default_effort="high",
    ),
    _claude_model(
        "claude-sonnet-5",
        "Claude Sonnet 5",
        "The best combination of speed and intelligence. Fast.",
        bedrock_id="us.anthropic.claude-sonnet-5",
        default_effort="high",
    ),
    _claude_model(
        "claude-haiku-4-5-20251001",
        "Claude Haiku 4.5",
        "The fastest model. It takes no effort setting.",
        bedrock_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        default_effort=None,
    ),
]

OPENAI_GPT_MODELS: list[ModelOption] = [
    _gpt_model(
        "gpt-6-astra",
        "GPT-6 Astra",
        "Frontier intelligence for the most demanding work.",
        codex_efforts=_CODEX_EFFORTS,
        api_efforts=_OPENAI_API_EFFORTS_NO_NONE,
    ),
    _gpt_model(
        "gpt-6-sol",
        "GPT-6 Sol",
        "Workhorse model for everyday work.",
        codex_efforts=_CODEX_EFFORTS,
        api_efforts=_OPENAI_API_EFFORTS,
    ),
    _gpt_model(
        "gpt-6-luna",
        "GPT-6 Luna",
        "Fast and affordable model for easier tasks.",
        codex_efforts=_CODEX_EFFORTS_NO_ULTRA,
        api_efforts=_OPENAI_API_EFFORTS,
    ),
]

_AUTH_METHOD_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    "anthropic_claude": {
        "cli": ("Claude Code CLI", "Runs the signed-in claude command on this server."),
        "api_key": ("Anthropic API key", "Calls the Claude API with a key held for this session."),
        "bedrock": ("AWS Bedrock", "Calls Claude on Bedrock with an AWS profile or access keys."),
    },
    "openai_gpt": {
        "cli": ("Codex CLI", "Runs the signed-in codex command on this server."),
        "api_key": ("OpenAI API key", "Calls the OpenAI Responses API with a key held for this session."),
    },
}

EFFORT_LABELS: dict[str, str] = {
    "none": "None",
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "xhigh": "Extra high",
    "max": "Max",
    "ultra": "Ultra",
}


def models_for(engine_id: str) -> list[ModelOption]:
    if engine_id == "anthropic_claude":
        return CLAUDE_MODELS
    if engine_id == "openai_gpt":
        return OPENAI_GPT_MODELS
    return []


def auth_methods_for(engine_id: str) -> list[AuthMethod]:
    """The auth methods an engine offers, in the order the form lists them."""
    methods: list[AuthMethod] = ["cli", "api_key", "bedrock"]
    return [method for method in methods if method in _AUTH_METHOD_LABELS.get(engine_id, {})]


def auth_method_option(
    engine_id: str, method: AuthMethod, *, ready: bool, note: str
) -> AuthMethodOption:
    label, summary = _AUTH_METHOD_LABELS[engine_id][method]
    return AuthMethodOption(id=method, label=label, summary=summary, ready=ready, note=note)


def auth_method_label(engine_id: str, method: str) -> str:
    return _AUTH_METHOD_LABELS[engine_id][method][0]


def method_support(engine_id: str, model_id: str, method: str) -> ModelMethodSupport | None:
    for model in models_for(engine_id):
        if model.id != model_id:
            continue
        for support in model.methods:
            if support.auth_method == method:
                return support
    return None


def model_label(engine_id: str, model_id: str) -> str:
    for model in models_for(engine_id):
        if model.id == model_id:
            return model.label
    return model_id


def provider_model_id(engine_id: str, model_id: str, method: str) -> str:
    support = method_support(engine_id, model_id, method)
    return support.provider_model_id if support is not None else model_id


def resolve_effort(
    engine_id: str,
    model_id: str,
    method: str,
    requested: ReasoningEffort | None,
) -> ReasoningEffort | None:
    """Return the effort to send, or raise a 422 when the model does not take it.

    A missing effort selects the model's default. A model without an effort
    setting (Claude Haiku 4.5) always resolves to None.
    """
    support = method_support(engine_id, model_id, method)
    engine_label = "Anthropic Claude" if engine_id == "anthropic_claude" else "OpenAI GPT"
    if support is None:
        raise AppError(
            422,
            "MODEL_NOT_SUPPORTED",
            f"{model_label(engine_id, model_id)} is not offered through "
            f"{auth_method_label(engine_id, method)}.",
            f"Choose a model listed for {engine_label} with this auth method.",
        )
    if not support.efforts:
        return None
    if requested is None:
        return support.default_effort
    if requested not in support.efforts:
        allowed = ", ".join(EFFORT_LABELS[effort] for effort in support.efforts)
        raise AppError(
            422,
            "EFFORT_NOT_SUPPORTED",
            f"{model_label(engine_id, model_id)} through "
            f"{auth_method_label(engine_id, method)} does not take the "
            f"{EFFORT_LABELS[requested]} effort.",
            f"Choose one of: {allowed}.",
        )
    return requested
