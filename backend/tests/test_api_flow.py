"""Full API flow tests over httpx AsyncClient + ASGITransport."""

import asyncio
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

import backend.app.main as main_module

SCENARIO = {
    "id": "test-dxa",
    "title": "DXA Bone Density Study",
    "summary_subtitle": "Estrogen-deficient Medicare beneficiary, first DXA",
    "member": {
        "name": "Alma Rivera",
        "member_id": "M-2201",
        "date_of_birth": "1951-09-02",
        "plan_type": "medicare_advantage",
        "plan_name": "Example MA HMO",
    },
    "provider": {
        "name": "Dr. Lee Endo",
        "npi": "9876543210",
        "specialty": "Endocrinology",
        "organization": "Example Medical Group",
    },
    "service": {
        "description": "DXA bone density study, axial skeleton",
        "cpt_codes": ["77080"],
        "icd10_codes": ["Z78.0"],
        "setting": "outpatient",
        "urgency": "standard",
    },
    "clinical_documents": [
        {
            "id": "doc-1",
            "title": "Endocrinology Note",
            "doc_type": "progress_note",
            "date": "2026-06-15",
            "text": (
                "Patient is estrogen-deficient and at clinical risk for osteoporosis. "
                "Ordered by treating physician after evaluation of need. "
                "No prior bone mass measurement on record."
            ),
        }
    ],
    "policy": {
        "source_type": "ncd",
        "code": "NCD 150.3",
        "title": "Bone (Mineral) Density Studies",
        "version": "2",
        "ncd_id": "150.3",
        "ncd_version": "2",
    },
    "expected_path": "approve",
    "criteria": [
        {
            "criterion_id": "BMD-1",
            "criterion_text": "Ordered by the treating physician following an evaluation of need",
            "depth": 0,
            "logic": None,
        },
        {
            "criterion_id": "BMD-4",
            "criterion_text": "Beneficiary falls into at least one qualifying category",
            "depth": 0,
            "logic": "ANY_ONE_OF",
        },
    ],
    "criteria_facts": {
        "BMD-1": {
            "status": "MET",
            "evidence": [
                {
                    "quote": "Ordered by treating physician after evaluation of need.",
                    "source_document": "Endocrinology Note",
                    "document_date": "2026-06-15",
                }
            ],
            "rationale": "Order documented by the treating provider.",
            "confidence": 95,
        },
        "BMD-4": {
            "status": "MET",
            "evidence": [
                {
                    "quote": "Patient is estrogen-deficient and at clinical risk for osteoporosis.",
                    "source_document": "Endocrinology Note",
                    "document_date": "2026-06-15",
                }
            ],
            "rationale": "Qualifying category one is documented.",
            "confidence": 93,
        },
    },
}


@pytest.fixture
def patched_scenarios(monkeypatch: pytest.MonkeyPatch):
    scenarios = [SCENARIO]

    def fake_get_scenario(scenario_id: str):
        return next((s for s in scenarios if s["id"] == scenario_id), None)

    monkeypatch.setattr(main_module, "get_scenarios", lambda: scenarios)
    monkeypatch.setattr(main_module, "get_scenario", fake_get_scenario)
    monkeypatch.setattr(main_module.settings, "mock_processing_seconds", 0.0)
    return scenarios


@pytest.fixture
async def client(patched_scenarios):
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def poll_evaluation(client: AsyncClient, request_id: str, eval_id: str) -> dict:
    for _ in range(200):
        response = await client.get(f"/api/requests/{request_id}/evaluations/{eval_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"completed", "failed"}:
            return body
        await asyncio.sleep(0.02)
    raise AssertionError("Evaluation never completed")


async def create_and_complete(client: AsyncClient, **extra) -> dict:
    """Create a request (auto-runs its evaluation) and wait for completion."""
    created = await client.post("/api/requests", json={"scenario_id": "test-dxa", **extra})
    assert created.status_code == 201
    body = created.json()
    await poll_evaluation(client, body["id"], body["latest_eval_id"])
    return (await client.get(f"/api/requests/{body['id']}")).json()


async def test_health_and_scenarios(client: AsyncClient) -> None:
    health = await client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert set(body["capabilities"]) == {
        "anthropic_claude_enabled",
        "openai_gpt_enabled",
    }

    scenarios = await client.get("/api/scenarios")
    assert scenarios.status_code == 200
    listing = scenarios.json()
    assert listing[0]["id"] == "test-dxa"
    assert listing[0]["expected_path"] == "approve"
    assert "150.3" in listing[0]["policy_label"]

    engines = await client.get("/api/engines")
    assert engines.status_code == 200
    engine_ids = {engine["id"] for engine in engines.json()}
    assert engine_ids == {"offline", "anthropic_claude", "openai_gpt"}
    offline = next(e for e in engines.json() if e["id"] == "offline")
    assert offline["available"] is True

    old_engine = await client.post(
        "/api/requests", json={"scenario_id": "test-dxa", "engine": "bedrock"}
    )
    assert old_engine.status_code == 422


async def test_intake_auto_runs_evaluation(client: AsyncClient) -> None:
    created = await client.post("/api/requests", json={"scenario_id": "test-dxa"})
    assert created.status_code == 201
    request_body = created.json()
    request_id = request_body["id"]
    assert request_id.startswith("PA-")
    assert request_body["determination_status"] == "in_review"
    assert request_body["latest_eval_id"].startswith("EV-")
    assert request_body["audit_trail"][0]["event"] == "request_created"
    assert request_body["audit_trail"][0]["actor"] == "Intake Automation"

    completed = await poll_evaluation(client, request_id, request_body["latest_eval_id"])
    assert completed["status"] == "completed"
    assert completed["error"] is None
    determination = completed["determination"]
    assert determination["recommendation"] == "approve"
    assert determination["criteria_met"] == "2/2 required criteria met"
    assert determination["coverage_check"]["ncd_id"] == "150.3"
    assert determination["coverage_check"]["policy_id"] == "150.3"
    assert determination["coverage_check"]["source_type"] == "ncd"
    assert determination["attribution"]["engine"] == "offline"
    assert determination["attribution"]["policy_source_type"] == "ncd"
    assert determination["attribution"]["policy_code"] == "NCD 150.3"
    assert determination["attribution"]["policy_version"] == "2"

    request_after = (await client.get(f"/api/requests/{request_id}")).json()
    assert request_after["processing_status"] == "completed"
    assert request_after["determination_status"] == "in_review"
    events = [event["event"] for event in request_after["audit_trail"]]
    assert "evaluation_started" in events
    assert "evaluation_completed" in events
    completed_event = next(
        event for event in request_after["audit_trail"] if event["event"] == "evaluation_completed"
    )
    assert completed_event["actor"].startswith("System — ")

    listing = await client.get("/api/requests")
    assert listing.status_code == 200
    summary = listing.json()[0]
    assert summary["id"] == request_id
    assert summary["recommendation"] == "approve"


async def test_action_blocked_while_analyzing(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module.settings, "mock_processing_seconds", 0.5)
    created = await client.post("/api/requests", json={"scenario_id": "test-dxa"})
    request_id = created.json()["id"]

    action_early = await client.post(
        f"/api/requests/{request_id}/actions",
        json={"action": "approve", "note": "", "actor": "UM Reviewer"},
    )
    assert action_early.status_code == 409
    assert action_early.json()["error"]["code"] == "ACTION_NOT_ALLOWED"

    letter_early = await client.get(f"/api/requests/{request_id}/letter")
    assert letter_early.status_code == 404
    assert letter_early.json()["error"]["code"] == "LETTER_NOT_READY"
    assert letter_early.json()["error"]["correlation_id"]


async def test_approve_flow_letter_save_and_send(client: AsyncClient) -> None:
    request_after = await create_and_complete(client)
    request_id = request_after["id"]

    # Determination exists but no disposition yet — letter is not composed.
    letter_before_action = await client.get(f"/api/requests/{request_id}/letter")
    assert letter_before_action.status_code == 404
    assert letter_before_action.json()["error"]["code"] == "LETTER_NOT_READY"

    acted = await client.post(
        f"/api/requests/{request_id}/actions",
        json={
            "action": "approve",
            "note": "Concur with recommendation",
            "actor": "Medical Director",
            "valid_from": "2026-07-05",
            "valid_through": "2026-10-03",
        },
    )
    assert acted.status_code == 200
    acted_body = acted.json()
    assert acted_body["determination_status"] == "approved"
    assert acted_body["auth_valid_from"] == "2026-07-05"
    assert acted_body["auth_valid_through"] == "2026-10-03"
    action_event = acted_body["audit_trail"][-1]
    assert action_event["from_state"] == "in_review"
    assert action_event["to_state"] == "approved"
    assert action_event["actor"] == "UM Reviewer"

    letter = await client.get(f"/api/requests/{request_id}/letter")
    assert letter.status_code == 200
    letter_body = letter.json()
    assert letter_body["letter_type"] == "approval"
    assert letter_body["status"] == "draft"
    assert "Valid From: 2026-07-05" in letter_body["body"]
    assert "Valid Through: 2026-10-03" in letter_body["body"]
    assert "Offline" in letter_body["body"]
    assert "Coverage Policy: Medicare NCD 150.3 (Version 2)" in letter_body["body"]
    assert "[PLACEHOLDER]" not in letter_body["body"]
    assert "AI-ASSISTED DRAFT" not in letter_body["body"]
    assert "deny" not in letter_body["body"].lower()

    # Save an edit, then send.
    edited_body = letter_body["body"] + "\nAddendum: peer-to-peer available on request."
    saved = await client.post(
        f"/api/requests/{request_id}/letter",
        json={"body": edited_body, "action": "save"},
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "draft"
    assert saved.json()["body"] == edited_body

    sent = await client.post(
        f"/api/requests/{request_id}/letter",
        json={"body": edited_body, "action": "mark_ready"},
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "ready"

    tamper = await client.post(
        f"/api/requests/{request_id}/letter",
        json={"body": f"{edited_body}\nTampered after send.", "action": "save"},
    )
    assert tamper.status_code == 409
    assert tamper.json()["error"]["code"] == "LETTER_ALREADY_FINALIZED"
    assert (await client.get(f"/api/requests/{request_id}/letter")).json()["body"] == edited_body

    final_request = (await client.get(f"/api/requests/{request_id}")).json()
    assert final_request["notified_at"]
    events = [event["event"] for event in final_request["audit_trail"]]
    assert "letter_edited" in events
    assert "letter_sent" in events

    summary = (await client.get("/api/requests")).json()[0]
    assert summary["notified_at"]

    # A second disposition on the same case is rejected.
    again = await client.post(
        f"/api/requests/{request_id}/actions",
        json={"action": "approve", "note": "", "actor": "UM Reviewer"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ALREADY_DISPOSED"


async def test_pend_requires_specific_items_and_renders_them(client: AsyncClient) -> None:
    request_after = await create_and_complete(client)
    request_id = request_after["id"]

    missing_items = await client.post(
        f"/api/requests/{request_id}/actions",
        json={"action": "pend", "note": "", "actor": "UM Reviewer"},
    )
    assert missing_items.status_code == 422
    assert missing_items.json()["error"]["code"] == "PEND_ITEMS_REQUIRED"

    acted = await client.post(
        f"/api/requests/{request_id}/actions",
        json={
            "action": "pend",
            "note": "",
            "actor": "UM Reviewer",
            "requested_items": [
                "Prior bone mass measurement report, if any",
                "Documentation of estrogen deficiency evaluation",
            ],
        },
    )
    assert acted.status_code == 200
    assert acted.json()["determination_status"] == "pended"
    assert len(acted.json()["requested_items"]) == 2

    letter = await client.get(f"/api/requests/{request_id}/letter")
    assert letter.status_code == 200
    body = letter.json()["body"]
    assert "1. Prior bone mass measurement report, if any" in body
    assert "2. Documentation of estrogen deficiency evaluation" in body
    assert "Response Deadline:" in body
    assert "[PLACEHOLDER]" not in body
    assert "not an adverse determination" in body


async def test_refer_md_requires_summary_and_composes_no_letter(client: AsyncClient) -> None:
    request_after = await create_and_complete(client)
    request_id = request_after["id"]

    missing_note = await client.post(
        f"/api/requests/{request_id}/actions",
        json={"action": "refer_md", "note": "   ", "actor": "UM Reviewer"},
    )
    assert missing_note.status_code == 422
    assert missing_note.json()["error"]["code"] == "MD_SUMMARY_REQUIRED"

    acted = await client.post(
        f"/api/requests/{request_id}/actions",
        json={
            "action": "refer_md",
            "note": "Atypical presentation; recommend MD review of category evidence.",
            "actor": "UM Reviewer",
        },
    )
    assert acted.status_code == 200
    assert acted.json()["determination_status"] == "referred_md"
    assert acted.json()["md_summary"].startswith("Atypical presentation")

    letter = await client.get(f"/api/requests/{request_id}/letter")
    assert letter.status_code == 409
    assert letter.json()["error"]["code"] == "NO_LETTER_FOR_REFERRAL"


async def test_seed_creates_worklist(client: AsyncClient) -> None:
    seeded = await client.post("/api/requests/seed", json={})
    assert seeded.status_code == 201
    summaries = seeded.json()
    assert len(summaries) == 1
    assert summaries[0]["id"].startswith("PA-")
    assert summaries[0]["scenario_id"] == "test-dxa"


async def test_seed_is_idempotent(client: AsyncClient) -> None:
    first = await client.post("/api/requests/seed", json={})
    assert len(first.json()) == 1
    first_ids = {row["id"] for row in first.json()}

    # Seeding again must not duplicate scenarios already present in the session.
    second = await client.post("/api/requests/seed", json={})
    assert second.status_code == 201
    assert len(second.json()) == 1
    assert {row["id"] for row in second.json()} == first_ids


async def test_worklist_sorts_expedited_first(client: AsyncClient) -> None:
    standard = await client.post("/api/requests", json={"scenario_id": "test-dxa"})
    expedited = await client.post(
        "/api/requests", json={"scenario_id": "test-dxa", "urgency": "expedited"}
    )
    assert standard.status_code == 201
    assert expedited.status_code == 201

    listing = (await client.get("/api/requests")).json()
    assert listing[0]["id"] == expedited.json()["id"]
    assert listing[0]["urgency"] == "expedited"
    assert listing[1]["id"] == standard.json()["id"]


async def test_unknown_scenario_and_request_ids(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_scenario = await client.post("/api/requests", json={"scenario_id": "nope"})
    assert missing_scenario.status_code == 404
    assert missing_scenario.json()["error"]["code"] == "SCENARIO_NOT_FOUND"

    missing_request = await client.get("/api/requests/PA-9999")
    assert missing_request.status_code == 404
    assert missing_request.json()["error"]["code"] == "REQUEST_NOT_FOUND"

    monkeypatch.setattr(main_module.settings, "mock_processing_seconds", 0.5)
    created = await client.post("/api/requests", json={"scenario_id": "test-dxa"})
    request_id = created.json()["id"]
    not_ready = await client.get(f"/api/requests/{request_id}/determination")
    assert not_ready.status_code == 404
    assert not_ready.json()["error"]["code"] == "DETERMINATION_NOT_READY"


async def test_registry_fallback_populates_error_notice(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ExplodingEngine:
        id = "openai_gpt"
        label = "Stub OpenAI GPT"
        description = "Always raises."
        model_id = None

        async def evaluate(self, request, scenario, settings):
            from backend.app.engines.trace import record_llm_trace
            from backend.app.schemas import LlmTrace

            record_llm_trace(
                LlmTrace(
                    provider="openai",
                    engine="openai_gpt",
                    engine_label=self.label,
                    model_id=settings.codex_model_id,
                    created_at="2026-07-07T00:00:00+00:00",
                    status="failed",
                    prompt="stub prompt",
                    request_payload={
                        "runner": "codex_cli",
                        "model": settings.codex_model_id,
                        "reasoning_effort": settings.codex_effort,
                    },
                    raw_response="",
                    response_text="",
                    error="model exploded",
                )
            )
            raise RuntimeError("model exploded")

        def availability(self, settings):
            return True, ""

    from backend.app.engines.rubric import RubricEngine

    monkeypatch.setattr(
        main_module.registry,
        "_engines",
        {"offline": RubricEngine(), "openai_gpt": ExplodingEngine()},
    )
    monkeypatch.setattr(
        main_module.registry, "is_available", lambda engine, settings: (True, "")
    )

    created = await client.post(
        "/api/requests", json={"scenario_id": "test-dxa", "engine": "openai_gpt"}
    )
    assert created.status_code == 201
    body = created.json()

    completed = await poll_evaluation(client, body["id"], body["latest_eval_id"])
    assert completed["status"] == "completed"
    assert completed["determination"]["attribution"]["engine"] == "offline"
    assert "Stub OpenAI GPT unavailable — fell back to Offline" in completed["error"]
    assert "model exploded" in completed["error"]

    inspection = await client.get(f"/api/requests/{body['id']}/llm-inspection")
    assert inspection.status_code == 200
    inspection_body = inspection.json()
    assert inspection_body["final_engine"] == "offline"
    assert inspection_body["traces"][0]["engine"] == "openai_gpt"
    assert inspection_body["traces"][0]["status"] == "failed"
    assert inspection_body["traces"][0]["request_payload"]["model"] == "gpt-5.5"
    assert inspection_body["traces"][0]["request_payload"]["reasoning_effort"] == "xhigh"


async def test_rerun_resets_disposition_and_letter(client: AsyncClient) -> None:
    request_after = await create_and_complete(client)
    request_id = request_after["id"]

    acted = await client.post(
        f"/api/requests/{request_id}/actions",
        json={"action": "approve", "note": "", "actor": "UM Reviewer"},
    )
    assert acted.status_code == 200
    assert (await client.get(f"/api/requests/{request_id}/letter")).status_code == 200

    rerun = await client.post(
        f"/api/requests/{request_id}/evaluations", json={"engine": "offline"}
    )
    assert rerun.status_code == 202
    await poll_evaluation(client, request_id, rerun.json()["id"])

    request_body = (await client.get(f"/api/requests/{request_id}")).json()
    assert request_body["determination_status"] == "in_review"
    assert request_body["auth_valid_from"] is None
    # The stale letter draft is gone until a fresh disposition is recorded.
    letter = await client.get(f"/api/requests/{request_id}/letter")
    assert letter.status_code == 404


async def test_engine_config_defaults_expose_auth_styles(client: AsyncClient) -> None:
    response = await client.get("/api/engine-config")
    assert response.status_code == 200
    by_engine = {entry["engine"]: entry for entry in response.json()}
    assert set(by_engine) == {"offline", "anthropic_claude", "openai_gpt"}
    assert by_engine["offline"]["auth_style"] == "none"
    assert by_engine["anthropic_claude"]["auth_style"] == "aws_bedrock"
    claude = by_engine["anthropic_claude"]["anthropic_claude"]
    assert claude["is_override"] is False
    assert claude["auth_method"] == "profile"
    # An empty profile means the standard AWS credential chain.
    assert claude["aws_profile"] == ""
    assert claude["region"] == "us-west-2"
    assert claude["model_id"] == "us.anthropic.claude-sonnet-5"
    assert claude["effort"] == "high"
    assert by_engine["openai_gpt"]["auth_style"] == "codex_cli"
    # Defaults are not session overrides yet.
    gpt = by_engine["openai_gpt"]["openai_gpt"]
    assert gpt["is_override"] is False
    assert gpt["command"] == "codex"
    assert gpt["model_id"] == "gpt-5.5"
    assert gpt["effort"] == "xhigh"

    engines = {entry["id"]: entry for entry in (await client.get("/api/engines")).json()}
    assert engines["anthropic_claude"]["model_id"] == "us.anthropic.claude-sonnet-5"
    assert engines["openai_gpt"]["model_id"] == "gpt-5.5"
    assert "default AWS credential chain" in engines["anthropic_claude"]["availability_note"]
    assert "codex" in engines["openai_gpt"]["availability_note"]


async def test_anthropic_claude_config_override_masks_secret_and_reflects_in_engines(
    client: AsyncClient,
) -> None:
    saved = await client.put(
        "/api/engine-config/anthropic-claude",
        json={
            "auth_method": "access_keys",
            "region": "us-west-2",
            "model_id": "us.anthropic.claude-sonnet-5",
            "effort": "medium",
            "aws_access_key_id": "AKIAEXAMPLE12345",
            "aws_secret_access_key": "top-secret-value",
        },
    )
    assert saved.status_code == 200
    claude = saved.json()["anthropic_claude"]
    assert claude["is_override"] is True
    assert claude["auth_method"] == "access_keys"
    assert claude["region"] == "us-west-2"
    assert claude["effort"] == "medium"
    assert claude["access_keys_configured"] is True
    # The raw secret is never returned anywhere in the payload.
    assert "top-secret-value" not in str(saved.json())
    assert claude["access_key_id_hint"] == "AKI...345"

    # The override propagates to the engines listing (model + availability note).
    engines = {e["id"]: e for e in (await client.get("/api/engines")).json()}
    assert engines["anthropic_claude"]["model_id"] == "us.anthropic.claude-sonnet-5"
    assert "us-west-2" in engines["anthropic_claude"]["availability_note"]
    assert "top-secret-value" not in str(engines)

    # Saving provider tweaks with blank secret fields preserves the session keys.
    updated = await client.put(
        "/api/engine-config/anthropic-claude",
        json={
            "auth_method": "access_keys",
            "region": "us-east-1",
            "model_id": "us.anthropic.claude-sonnet-5[1m]",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["anthropic_claude"]["model_id"] == "us.anthropic.claude-sonnet-5"
    assert updated.json()["anthropic_claude"]["effort"] == "high"
    assert updated.json()["anthropic_claude"]["access_keys_configured"] is True
    engines_after_update = {e["id"]: e for e in (await client.get("/api/engines")).json()}
    assert engines_after_update["anthropic_claude"]["available"] is True

    # DELETE resets to the process defaults.
    reset = await client.delete("/api/engine-config/anthropic-claude")
    assert reset.status_code == 200
    assert reset.json()["anthropic_claude"]["is_override"] is False
    assert reset.json()["anthropic_claude"]["auth_method"] == "profile"
    assert reset.json()["anthropic_claude"]["aws_profile"] == ""
    assert reset.json()["anthropic_claude"]["region"] == "us-west-2"
    assert reset.json()["anthropic_claude"]["model_id"] == "us.anthropic.claude-sonnet-5"
    assert reset.json()["anthropic_claude"]["effort"] == "high"


async def test_anthropic_claude_access_keys_require_both_keys(client: AsyncClient) -> None:
    response = await client.put(
        "/api/engine-config/anthropic-claude",
        json={
            "auth_method": "access_keys",
            "region": "us-west-2",
            "model_id": "us.anthropic.claude-sonnet-5",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BEDROCK_KEYS_REQUIRED"


async def test_openai_gpt_config_override_and_reset(client: AsyncClient) -> None:
    saved = await client.put(
        "/api/engine-config/openai-gpt",
        json={"command": "codex", "model_id": "gpt-5.4-mini", "effort": "medium"},
    )
    assert saved.status_code == 200
    assert saved.json()["openai_gpt"]["model_id"] == "gpt-5.4-mini"
    assert saved.json()["openai_gpt"]["effort"] == "medium"
    assert saved.json()["openai_gpt"]["is_override"] is True

    engines = {e["id"]: e for e in (await client.get("/api/engines")).json()}
    assert engines["openai_gpt"]["model_id"] == "gpt-5.4-mini"

    reset = await client.delete("/api/engine-config/openai-gpt")
    assert reset.json()["openai_gpt"]["is_override"] is False
    assert reset.json()["openai_gpt"]["command"] == "codex"
    assert reset.json()["openai_gpt"]["model_id"] == "gpt-5.5"
    assert reset.json()["openai_gpt"]["effort"] == "xhigh"


async def test_model_selectors_reject_unsupported_values(client: AsyncClient) -> None:
    bad_claude = await client.put(
        "/api/engine-config/anthropic-claude",
        json={
            "auth_method": "profile",
            "region": "us-west-2",
            "model_id": "not-a-claude-model",
            "effort": "high",
        },
    )
    assert bad_claude.status_code == 422

    bad_gpt = await client.put(
        "/api/engine-config/openai-gpt",
        json={"command": "codex", "model_id": "codex-auto-review", "effort": "xhigh"},
    )
    assert bad_gpt.status_code == 422

    bad_command = await client.put(
        "/api/engine-config/openai-gpt",
        json={"command": "yes", "model_id": "gpt-5.5", "effort": "xhigh"},
    )
    assert bad_command.status_code == 422


async def test_coverage_route(client: AsyncClient) -> None:
    found = await client.get("/api/coverage/150.3")
    assert found.status_code == 200
    body = found.json()
    assert body["policy_id"] == "150.3"
    assert body["source_type"] == "ncd"
    assert body["ncd_id"] == "150.3"
    assert body["version"] == "2"
    assert body["ncd_version"] == "2"
    assert body["lcd_id"] is None
    assert body["covered"] is True
    assert body["title"] == "Bone (Mineral) Density Studies"
    assert body["source_url"]

    for alias in ("ncd-150-3", "NCD%20150.3", "150-3"):
        aliased = await client.get(f"/api/coverage/{alias}")
        assert aliased.status_code == 200, alias
        assert aliased.json()["policy_id"] == "150.3"

    for missing_id in ("999.9", "L00000", "not-a-policy"):
        missing = await client.get(f"/api/coverage/{missing_id}")
        assert missing.status_code == 404, missing_id
        assert missing.json()["error"]["code"] == "COVERAGE_NOT_FOUND"


async def test_policy_lookup_returns_local_ncd_document(client: AsyncClient) -> None:
    found = await client.get("/api/policies/150.3")
    assert found.status_code == 200
    body = found.json()
    assert body["policy_id"] == "150.3"
    assert body["source_type"] == "ncd"
    assert body["code"] == "NCD 150.3"
    assert body["version"] == "2"
    assert body["title"] == "Bone (Mineral) Density Studies"
    assert body["local_file_available"] is True
    assert body["criteria"], "The local NCD file should supply policy criteria."
    assert all(criterion["text"] for criterion in body["criteria"])
    assert body["sections"], "The local NCD file should supply full-text sections."
    review = body["review_criteria"]
    assert [item["scenario_id"] for item in review] == ["test-dxa"]
    assert [c["criterion_id"] for c in review[0]["criteria"]] == [
        c["criterion_id"] for c in SCENARIO["criteria"]
    ]

    aliased = await client.get("/api/policies/ncd-150-3")
    assert aliased.status_code == 200
    assert aliased.json()["policy_id"] == "150.3"


async def test_policy_lookup_unknown_ids_return_404(client: AsyncClient) -> None:
    for missing_id in ("L99999", "999.9", "nope"):
        missing = await client.get(f"/api/policies/{missing_id}")
        assert missing.status_code == 404, missing_id
        error = missing.json()["error"]
        assert error["code"] == "POLICY_NOT_FOUND"
        assert error["retry_guidance"]


async def test_cms_0057_sla_clocks(client: AsyncClient) -> None:
    standard = (await client.post("/api/requests", json={"scenario_id": "test-dxa"})).json()
    standard_window = datetime.fromisoformat(standard["sla_due_at"]) - datetime.fromisoformat(
        standard["created_at"]
    )
    assert standard_window.total_seconds() == 7 * 24 * 3600

    expedited = (
        await client.post(
            "/api/requests", json={"scenario_id": "test-dxa", "urgency": "expedited"}
        )
    ).json()
    assert expedited["service"]["urgency"] == "expedited"
    expedited_window = datetime.fromisoformat(expedited["sla_due_at"]) - datetime.fromisoformat(
        expedited["created_at"]
    )
    assert expedited_window.total_seconds() == 72 * 3600
