"""Prior Auth Express — FastAPI application (routes per docs/api-contract.md)."""

import asyncio
import copy
from datetime import timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings, get_settings
from .data.scenarios import get_scenario, get_scenarios
from .engines.anthropic_claude import AnthropicClaudeEngine
from .engines.base import EngineRegistry, claude_method_readiness, openai_gpt_method_readiness
from .engines.catalog import auth_method_option, auth_methods_for, models_for, resolve_effort
from .engines.openai_gpt import OpenAiGptEngine
from .engines.rubric import RubricEngine
from .engines.trace import begin_llm_trace_capture, end_llm_trace_capture
from .errors import AppError, app_error_handler
from .schemas import (
    AuthMethodOption,
    ClaudeConfigInput,
    CoverageCheck,
    Determination,
    EngineConfig,
    EngineId,
    EngineInfo,
    EvaluationRequest,
    EvaluationStatus,
    HealthStatus,
    HumanActionRequest,
    Letter,
    LetterUpdateRequest,
    LlmInspection,
    OpenAiGptConfigInput,
    PARequest,
    PARequestSummary,
    PolicyDocument,
    ScenarioSummary,
    Urgency,
)
from .services.coverage import load_coverage_check
from .services.letters import compose_letter
from .services.policies import load_policy_document, scenario_policy_label
from .state import SessionManager, SessionState, runtime_capabilities

settings = get_settings()
session_manager = SessionManager(settings=settings)
registry = EngineRegistry(
    {
        "offline": RubricEngine(),
        "anthropic_claude": AnthropicClaudeEngine(),
        "openai_gpt": OpenAiGptEngine(),
    }
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = PROJECT_ROOT / "dist"

try:
    APP_VERSION = (PROJECT_ROOT / "VERSION").read_text().strip()
except OSError:
    APP_VERSION = "0.0.0"

app = FastAPI(title="Prior Auth Express", version=APP_VERSION)
app.add_exception_handler(AppError, app_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)


class CreateRequestBody(BaseModel):
    scenario_id: str
    urgency: Urgency | None = None
    engine: EngineId = "offline"


class SeedRequestBody(BaseModel):
    engine: EngineId = "offline"


def _current_session(request: Request) -> SessionState:
    session = getattr(request.state, "pa_session", None)
    if session is None:
        raise RuntimeError("Request session was not initialized.")
    return session


@app.middleware("http")
async def session_and_security_middleware(request: Request, call_next):
    session_id = request.cookies.get(settings.session_cookie_name)
    current_session_id, session, _ = await session_manager.get_or_create(session_id)
    request.state.pa_session = session
    request.state.pa_session_id = current_session_id

    response: Response = await call_next(request)

    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.set_cookie(
        key=settings.session_cookie_name,
        value=current_session_id,
        httponly=True,
        max_age=settings.session_idle_minutes * 60,
        path="/",
        samesite=settings.session_cookie_same_site,
        secure=settings.hosted_mode
        or settings.session_cookie_secure
        or settings.session_cookie_same_site == "none",
    )
    return response


@app.get("/api/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    return HealthStatus(
        status="ok",
        version=APP_VERSION,
        capabilities=runtime_capabilities(settings),
    )


@app.get("/api/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios() -> list[ScenarioSummary]:
    return [
        ScenarioSummary(
            id=scenario["id"],
            title=scenario.get("title", scenario["id"]),
            subtitle=scenario.get("summary_subtitle", ""),
            expected_path=scenario.get("expected_path", "pend"),
            policy_label=scenario_policy_label(scenario),
            plan_type=(scenario.get("member") or {}).get("plan_type", "commercial"),
        )
        for scenario in get_scenarios()
    ]


@app.get("/api/engines", response_model=list[EngineInfo])
async def list_engines(request: Request) -> list[EngineInfo]:
    session = _current_session(request)
    effective = session.engine_config.effective_settings(settings)
    return registry.list_engines(effective)


@app.get("/api/requests", response_model=list[PARequestSummary])
async def list_requests(request: Request) -> list[PARequestSummary]:
    return _current_session(request).cases.list_summaries()


async def _intake(
    session: SessionState, scenario: dict, engine_id: str
) -> PARequest:
    """Create a request and immediately start its evaluation (ambient intelligence)."""
    pa_request = await session.cases.create_from_scenario(scenario)
    evaluation = await session.cases.create_evaluation(pa_request.id, engine_id)
    asyncio.create_task(_run_evaluation(session, pa_request.id, evaluation.id, engine_id))
    return pa_request


@app.post("/api/requests", response_model=PARequest, status_code=201)
async def create_request(request: Request, body: CreateRequestBody) -> PARequest:
    scenario = get_scenario(body.scenario_id)
    if scenario is None:
        raise AppError(
            404,
            "SCENARIO_NOT_FOUND",
            f"Scenario '{body.scenario_id}' was not found.",
            "Choose a scenario from GET /api/scenarios.",
        )
    if body.urgency is not None:
        scenario = copy.deepcopy(scenario)
        scenario.setdefault("service", {})["urgency"] = body.urgency
    registry.get(body.engine)
    session = _current_session(request)
    return await _intake(session, scenario, body.engine)


# One scenario arrives expedited so the seeded queue demonstrates the CMS-0057-F
# expedited-first ordering.
_SEED_EXPEDITED = {"ncd-20-32-tavr"}


@app.post("/api/requests/seed", response_model=list[PARequestSummary], status_code=201)
async def seed_requests(request: Request, body: SeedRequestBody) -> list[PARequestSummary]:
    """Load the sample caseload once. Idempotent: scenarios already present in this
    session are skipped, so repeated clicks never duplicate cases."""
    registry.get(body.engine)
    session = _current_session(request)
    already_loaded = session.cases.loaded_scenario_ids()
    for scenario in get_scenarios():
        if scenario["id"] in already_loaded:
            continue
        if scenario["id"] in _SEED_EXPEDITED:
            scenario = copy.deepcopy(scenario)
            scenario.setdefault("service", {})["urgency"] = "expedited"
        await _intake(session, scenario, body.engine)
    return session.cases.list_summaries()


@app.get("/api/requests/{request_id}", response_model=PARequest)
async def get_request(request: Request, request_id: str) -> PARequest:
    return _current_session(request).cases.get(request_id)


async def _run_evaluation(
    session: SessionState, request_id: str, eval_id: str, engine_id: str
) -> None:
    store = session.cases
    evaluation = store.get_evaluation(request_id, eval_id)
    pa_request = store.get(request_id)
    requested_engine = registry.get(engine_id)

    store.set_processing_status(request_id, "analyzing")
    evaluation.status = "analyzing"
    store.add_audit_event(
        request_id,
        "evaluation_started",
        f"System — {requested_engine.label}",
        from_state="queued",
        to_state="analyzing",
    )

    scenario = get_scenario(pa_request.scenario_id or "") or {
        "policy": pa_request.policy.model_dump() if pa_request.policy else {},
        "criteria": [],
        "criteria_facts": {},
    }

    trace_token = begin_llm_trace_capture()
    trace_open = True
    try:
        effective = session.engine_config.effective_settings(settings)
        determination, error_notice = await registry.run(
            engine_id, pa_request, scenario, effective
        )
        if not determination.id:
            determination.id = eval_id
        store.set_determination(request_id, determination)
        evaluation.determination = determination
        evaluation.error = error_notice
        evaluation.status = "completed"
        store.set_processing_status(request_id, "completed")
        store.add_audit_event(
            request_id,
            "evaluation_completed",
            f"System — {determination.attribution.engine_label}",
            from_state="analyzing",
            to_state="completed",
        )
        traces = end_llm_trace_capture(trace_token)
        trace_open = False
        store.set_llm_inspection(
            request_id,
            LlmInspection(
                request_id=request_id,
                evaluation_id=eval_id,
                final_engine=determination.attribution.engine,
                final_engine_label=determination.attribution.engine_label,
                traces=traces,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — surface any unexpected failure as failed status
        traces = end_llm_trace_capture(trace_token) if trace_open else []
        if traces:
            store.set_llm_inspection(
                request_id,
                LlmInspection(
                    request_id=request_id,
                    evaluation_id=eval_id,
                    final_engine=requested_engine.id,
                    final_engine_label=requested_engine.label,
                    traces=traces,
                ),
            )
        message = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
        evaluation.error = message
        evaluation.status = "failed"
        store.set_processing_status(request_id, "failed")
        store.add_audit_event(
            request_id,
            "evaluation_failed",
            f"System — {requested_engine.label}",
            from_state="analyzing",
            to_state="failed",
        )


@app.post(
    "/api/requests/{request_id}/evaluations",
    response_model=EvaluationStatus,
    status_code=202,
)
async def start_evaluation(
    request: Request, request_id: str, body: EvaluationRequest
) -> EvaluationStatus:
    session = _current_session(request)
    registry.get(body.engine)
    evaluation = await session.cases.create_evaluation(request_id, body.engine)
    asyncio.create_task(_run_evaluation(session, request_id, evaluation.id, body.engine))
    return evaluation


@app.get(
    "/api/requests/{request_id}/evaluations/{eval_id}",
    response_model=EvaluationStatus,
)
async def get_evaluation(request: Request, request_id: str, eval_id: str) -> EvaluationStatus:
    return _current_session(request).cases.get_evaluation(request_id, eval_id)


@app.get("/api/requests/{request_id}/determination", response_model=Determination)
async def get_determination(request: Request, request_id: str) -> Determination:
    return _current_session(request).cases.get_determination(request_id)


@app.get("/api/requests/{request_id}/llm-inspection", response_model=LlmInspection)
async def get_llm_inspection(request: Request, request_id: str) -> LlmInspection:
    return _current_session(request).cases.get_llm_inspection(request_id)


@app.post("/api/requests/{request_id}/actions", response_model=PARequest)
async def apply_action(
    request: Request, request_id: str, body: HumanActionRequest
) -> PARequest:
    session = _current_session(request)
    return await session.cases.apply_action(request_id, body)


def _reviewer_zone(tz: str | None) -> tzinfo:
    if not tz:
        return timezone.utc
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


@app.get("/api/requests/{request_id}/letter", response_model=Letter)
async def get_letter(request: Request, request_id: str, tz: str | None = None) -> Letter:
    store = _current_session(request).cases
    pa_request = store.get(request_id)
    existing = store.get_letter(request_id)
    if existing is not None:
        return existing
    determination = store.latest_determination(request_id)
    if determination is None:
        raise AppError(
            404,
            "LETTER_NOT_READY",
            "A notification letter is not available until an evaluation completes and a "
            "human disposition is recorded.",
            "Run an evaluation and apply a reviewer action first.",
        )
    letter = compose_letter(
        pa_request, determination, pa_request.determination_status, _reviewer_zone(tz)
    )
    store.set_letter(request_id, letter)
    return letter


@app.post("/api/requests/{request_id}/letter", response_model=Letter)
async def update_letter(
    request: Request, request_id: str, body: LetterUpdateRequest
) -> Letter:
    store = _current_session(request).cases
    return store.update_letter(request_id, body.body, mark_ready=body.action == "mark_ready")


@app.get("/api/policies/{policy_id}", response_model=PolicyDocument)
async def get_policy(policy_id: str) -> PolicyDocument:
    """Local-only policy lookup: data/cms-coverage/ files plus scenario criteria."""
    return load_policy_document(policy_id, get_scenarios())


@app.get("/api/coverage/{policy_id}", response_model=CoverageCheck)
async def get_coverage(policy_id: str) -> CoverageCheck:
    return load_coverage_check(policy_id)


# --- Per-engine provider configuration (auth method, model, effort) ----------
# The form renders from the catalog and readiness notes; the routes validate
# every saved choice against the same catalog.


def _auth_method_options(engine_id: EngineId, effective: Settings) -> list[AuthMethodOption]:
    readiness = (
        claude_method_readiness if engine_id == "anthropic_claude" else openai_gpt_method_readiness
    )
    options: list[AuthMethodOption] = []
    for method in auth_methods_for(engine_id):
        ready, note = readiness(effective, method)
        options.append(auth_method_option(engine_id, method, ready=ready, note=note))
    return options


def _engine_config(session: SessionState, engine_id: EngineId) -> EngineConfig:
    config = EngineConfig(engine=engine_id)
    if engine_id == "offline":
        return config
    effective = session.engine_config.effective_settings(settings)
    config.auth_methods = _auth_method_options(engine_id, effective)
    config.models = models_for(engine_id)
    if engine_id == "anthropic_claude":
        config.anthropic_claude = session.engine_config.claude_view(settings)
    else:
        config.openai_gpt = session.engine_config.openai_gpt_view(settings)
    return config


@app.get("/api/engine-config", response_model=list[EngineConfig])
async def list_engine_config(request: Request) -> list[EngineConfig]:
    session = _current_session(request)
    return [_engine_config(session, engine_id) for engine_id in registry.engine_ids()]


@app.put("/api/engine-config/anthropic-claude", response_model=EngineConfig)
async def set_anthropic_claude_config(
    request: Request, body: ClaudeConfigInput
) -> EngineConfig:
    session = _current_session(request)
    effort = resolve_effort("anthropic_claude", body.model_id, body.auth_method, body.effort)
    current = session.engine_config.claude_view(settings)
    if body.auth_method == "api_key" and not body.api_key and not current.api_key_configured:
        raise AppError(
            400,
            "ANTHROPIC_KEY_REQUIRED",
            "An Anthropic API key is required for the API key method.",
            "Enter a key, or choose the Claude Code CLI or AWS Bedrock method.",
        )
    if (
        body.auth_method == "bedrock"
        and body.bedrock_credentials == "access_keys"
        and not (body.aws_access_key_id and body.aws_secret_access_key)
        and not current.access_keys_configured
    ):
        raise AppError(
            400,
            "BEDROCK_KEYS_REQUIRED",
            "Access key ID and secret access key are required for the access-keys credentials.",
            "Enter both keys, or choose the AWS profile to use the default credential chain.",
        )
    await session.engine_config.set_claude(body.model_copy(update={"effort": effort}))
    return _engine_config(session, "anthropic_claude")


@app.delete("/api/engine-config/anthropic-claude", response_model=EngineConfig)
async def clear_anthropic_claude_config(request: Request) -> EngineConfig:
    session = _current_session(request)
    await session.engine_config.clear_claude()
    return _engine_config(session, "anthropic_claude")


@app.put("/api/engine-config/openai-gpt", response_model=EngineConfig)
async def set_openai_gpt_config(
    request: Request, body: OpenAiGptConfigInput
) -> EngineConfig:
    session = _current_session(request)
    effort = resolve_effort("openai_gpt", body.model_id, body.auth_method, body.effort)
    current = session.engine_config.openai_gpt_view(settings)
    if body.auth_method == "api_key" and not body.api_key and not current.api_key_configured:
        raise AppError(
            400,
            "OPENAI_KEY_REQUIRED",
            "An OpenAI API key is required for the API key method.",
            "Enter a key, or choose the Codex CLI method.",
        )
    await session.engine_config.set_openai_gpt(body.model_copy(update={"effort": effort}))
    return _engine_config(session, "openai_gpt")


@app.delete("/api/engine-config/openai-gpt", response_model=EngineConfig)
async def clear_openai_gpt_config(request: Request) -> EngineConfig:
    session = _current_session(request)
    await session.engine_config.clear_openai_gpt()
    return _engine_config(session, "openai_gpt")


if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


def _safe_frontend_static_file(full_path: str) -> Path | None:
    try:
        dist_root = DIST_DIR.resolve()
        static_file = (DIST_DIR / full_path).resolve()
    except (OSError, RuntimeError):
        return None
    if not static_file.is_relative_to(dist_root):
        return None
    if not static_file.is_file():
        return None
    return static_file


@app.get("/", include_in_schema=False)
async def serve_frontend_index():
    index_path = DIST_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found. Run the frontend build first.")
    return FileResponse(index_path)


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found.")
    static_file = _safe_frontend_static_file(full_path)
    if static_file:
        return FileResponse(static_file)
    index_path = DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend build not found. Run the frontend build first.")
