"""Data invariants for the demo scenarios in backend/app/data/scenarios.py.

Most tests run once per scenario in SCENARIOS, so a new scenario is checked
without a test change. The PSG test checks the one scenario that must pend on a
missing Epworth score. The API tests use the real registry and check that seeding
loads each scenario once.
"""

import re

import pytest
from httpx import ASGITransport, AsyncClient

import backend.app.main as main_module
from backend.app.config import Settings
from backend.app.data.scenarios import SCENARIOS, get_scenario, get_scenarios
from backend.app.engines.rubric import RubricEngine
from backend.app.schemas import PARequest, PolicyRef
from backend.app.services.coverage import (
    contractor_name,
    document_version,
    find_policy_file,
    normalize_policy_id,
)
from backend.app.services.policies import load_policy_document

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
    assert determination.coverage_check is not None
    assert determination.coverage_check.source_type == scenario["policy"]["source_type"]

    facts = scenario["criteria_facts"]
    open_texts = [
        criterion["criterion_text"]
        for criterion in scenario["criteria"]
        if facts[criterion["criterion_id"]]["status"] != "MET"
    ]
    assert determination.gaps == open_texts
    met = len(scenario["criteria"]) - len(open_texts)
    assert determination.criteria_met == f"{met}/{len(scenario['criteria'])} required criteria met"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_criteria_nesting_is_well_formed(scenario: dict) -> None:
    criteria = scenario["criteria"]
    assert criteria[0]["depth"] == 0
    for previous, current in zip(criteria, criteria[1:]):
        assert current["depth"] <= previous["depth"] + 1, (
            f"{current['criterion_id']}: depth skips a level"
        )
        if current["depth"] > previous["depth"]:
            assert previous["logic"], (
                f"{previous['criterion_id']}: a parent criterion needs a logic label"
            )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_policy_matches_local_file(scenario: dict) -> None:
    policy = scenario["policy"]
    policy_file = find_policy_file(policy["code"])
    assert policy_file is not None, f"No local policy file for {policy['code']}"
    raw = policy_file.raw
    assert policy["title"] == raw["title"]
    assert policy["version"] == document_version(raw)
    assert policy["source_url"] == raw["source"]["mcd_url"]
    if policy["source_type"] == "lcd":
        assert policy["lcd_id"] == raw["lcd_id"]
        assert policy["contractor"] == contractor_name(raw)

    # Every criterion in the file has an authored criterion in the scenario.
    file_ids = {item["id"] for item in raw["criteria"]}
    scenario_ids = {criterion["criterion_id"] for criterion in scenario["criteria"]}
    assert file_ids <= scenario_ids

    document = load_policy_document(policy["code"], SCENARIOS)
    assert document.local_file_available
    review_sets = {item.scenario_id: item for item in document.review_criteria}
    assert scenario["id"] in review_sets
    assert [c.criterion_id for c in review_sets[scenario["id"]].criteria] == [
        criterion["criterion_id"] for criterion in scenario["criteria"]
    ]


# "Epworth" in any case, or the abbreviation "ESS" as a whole word.
_SLEEPINESS_SCALE = re.compile(r"(?i:epworth)|\bESS\b")


def test_psg_scenario_pends_only_on_missing_epworth_score() -> None:
    scenario = get_scenario("lcd-l33405-psg")
    assert scenario is not None
    open_items = [
        criterion_id
        for criterion_id, fact in scenario["criteria_facts"].items()
        if fact["status"] != "MET"
    ]
    assert open_items == ["PSG-3"]
    assert scenario["criteria_facts"]["PSG-3"]["status"] == "INSUFFICIENT"

    # The packet names the scale at most as a blank field. No line that names
    # it may carry a number, so no Epworth score exists anywhere.
    for document in scenario["clinical_documents"]:
        for line in document["text"].splitlines():
            if _SLEEPINESS_SCALE.search(line):
                assert not re.search(r"\d", line), (
                    f"{document['title']!r} has a possible Epworth score: {line!r}"
                )


@pytest.fixture
async def app_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main_module.settings, "mock_processing_seconds", 0.0)
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_api_lists_every_scenario(app_client: AsyncClient) -> None:
    response = await app_client.get("/api/scenarios")
    assert response.status_code == 200
    listing = {row["id"]: row for row in response.json()}
    assert list(listing) == SCENARIO_IDS
    for scenario in SCENARIOS:
        row = listing[scenario["id"]]
        assert row["expected_path"] == scenario["expected_path"]
        assert row["plan_type"] == scenario["member"]["plan_type"]
        assert row["policy_label"] == f"Medicare {scenario['policy']['code']}"


async def test_seed_loads_every_scenario_once(app_client: AsyncClient) -> None:
    first = await app_client.post("/api/requests/seed", json={})
    assert first.status_code == 201
    rows = first.json()
    assert sorted(row["scenario_id"] for row in rows) == sorted(SCENARIO_IDS)
    expedited = {row["scenario_id"] for row in rows if row["urgency"] == "expedited"}
    assert expedited == {"ncd-20-32-tavr"}

    second = await app_client.post("/api/requests/seed", json={})
    assert second.status_code == 201
    assert {row["id"] for row in second.json()} == {row["id"] for row in rows}
