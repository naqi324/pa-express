"""Data invariants for the demo scenarios in backend/app/data/scenarios.py.

Each test runs once per scenario in SCENARIOS, so a new scenario is checked
without a test change.
"""

import pytest

from backend.app.config import Settings
from backend.app.data.scenarios import SCENARIOS, get_scenario, get_scenarios
from backend.app.engines.rubric import RubricEngine
from backend.app.schemas import PARequest, PolicyRef
from backend.app.services.coverage import normalize_policy_id

SCENARIO_IDS = [scenario["id"] for scenario in SCENARIOS]


def test_scenario_ids_are_unique() -> None:
    assert SCENARIOS, "At least one scenario is required."
    assert len(SCENARIO_IDS) == len(set(SCENARIO_IDS))


def test_registry_accessors() -> None:
    assert get_scenarios() is SCENARIOS
    for scenario in SCENARIOS:
        assert get_scenario(scenario["id"]) is scenario
    assert get_scenario("no-such-scenario") is None


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_evidence_quotes_are_verbatim(scenario: dict) -> None:
    documents = {doc["title"]: doc for doc in scenario["clinical_documents"]}
    for criterion_id, fact in scenario["criteria_facts"].items():
        for citation in fact.get("evidence", []):
            source = citation["source_document"]
            assert source in documents, f"{criterion_id}: unknown document {source!r}"
            document = documents[source]
            assert citation["quote"] in document["text"], (
                f"{criterion_id}: quote is not verbatim in {source!r}"
            )
            assert citation["document_date"] == document["date"], (
                f"{criterion_id}: document_date does not match {source!r}"
            )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_criteria_and_facts_match_one_to_one(scenario: dict) -> None:
    criterion_ids = [criterion["criterion_id"] for criterion in scenario["criteria"]]
    assert criterion_ids, "A scenario needs at least one criterion."
    assert len(criterion_ids) == len(set(criterion_ids))
    assert set(scenario["criteria_facts"]) == set(criterion_ids)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_expected_path_matches_facts(scenario: dict) -> None:
    statuses = {fact["status"] for fact in scenario["criteria_facts"].values()}
    assert statuses <= {"MET", "NOT_MET", "INSUFFICIENT"}
    expected = "approve" if statuses == {"MET"} else "pend"
    assert scenario["expected_path"] == expected


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_met_facts_carry_evidence(scenario: dict) -> None:
    for criterion_id, fact in scenario["criteria_facts"].items():
        if fact["status"] == "MET":
            assert fact.get("evidence"), f"{criterion_id}: MET without evidence"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_policy_names_an_ncd_or_lcd(scenario: dict) -> None:
    policy = scenario["policy"]
    PolicyRef.model_validate(policy)
    assert policy["source_type"] in {"ncd", "lcd"}
    assert policy.get("code")
    assert policy.get("version")
    if policy["source_type"] == "ncd":
        assert policy.get("ncd_id") and policy.get("ncd_version")
        expected_code = f"NCD {policy['ncd_id']}"
    else:
        assert policy.get("lcd_id") and policy.get("contractor")
        expected_code = f"LCD {policy['lcd_id']}"
    assert policy["code"] == expected_code
    key = normalize_policy_id(policy["code"])
    assert key is not None and key.source_type == policy["source_type"]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
async def test_offline_engine_reaches_expected_path(scenario: dict) -> None:
    request = PARequest(
        id="PA-0001",
        scenario_id=scenario["id"],
        member=scenario["member"],
        provider=scenario["provider"],
        service=scenario["service"],
        clinical_documents=scenario["clinical_documents"],
        processing_status="queued",
        determination_status="in_review",
        policy=scenario["policy"],
        sla_due_at="2026-07-08T00:00:00+00:00",
        created_at="2026-07-05T00:00:00+00:00",
        audit_trail=[],
    )
    determination = await RubricEngine().evaluate(
        request, scenario, Settings(mock_processing_seconds=0.0)
    )
    assert determination.recommendation == scenario["expected_path"]
    assert determination.attribution.policy_source_type == scenario["policy"]["source_type"]
    assert determination.attribution.policy_code == scenario["policy"]["code"]
