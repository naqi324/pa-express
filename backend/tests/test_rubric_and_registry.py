"""Rubric decision matrix, engine registry fallback, policy, and provider tests.

The scenarios here are inline and synthetic. The default policy is a made-up
LCD, so these tests do not depend on any file in data/cms-coverage/.
"""

import asyncio
import json
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.engines.base import Engine, EngineRegistry
from backend.app.engines.bedrock import build_bedrock_converse_request, invoke_bedrock_converse
from backend.app.engines.codex import CodexEngine
from backend.app.engines.llm_common import (
    build_openai_source_skill_prompt,
    build_source_skill_prompt,
    determination_from_payload,
    llm_response_json_schema,
)
from backend.app.engines.rubric import RubricEngine
from backend.app.errors import AppError
from backend.app.schemas import Attribution, Determination, PARequest
from backend.app.services import coverage as coverage_module
from backend.app.services.coverage import load_coverage_check, normalize_policy_id
from backend.app.services.policies import letter_policy_line, load_policy_document

SYNTHETIC_LCD = {
    "source_type": "lcd",
    "code": "LCD L99999",
    "title": "Synthetic Test LCD",
    "version": "1",
    "lcd_id": "L99999",
    "contractor": "Example MAC",
}


def make_scenario(criteria_facts: dict, *, policy: dict | None = None) -> dict:
    return {
        "id": "test-knee",
        "title": "Total Knee Arthroplasty",
        "summary_subtitle": "Degenerative joint disease, conservative care failed",
        "member": {
            "name": "Pat Example",
            "member_id": "M-100",
            "date_of_birth": "1958-03-14",
            "plan_type": "commercial",
            "plan_name": "Example PPO",
        },
        "provider": {
            "name": "Dr. Casey Ortho",
            "npi": "1234567890",
            "specialty": "Orthopedic Surgery",
            "organization": "Example Orthopedics",
        },
        "service": {
            "description": "Total knee arthroplasty, right knee",
            "cpt_codes": ["27447"],
            "icd10_codes": ["M17.11"],
            "setting": "inpatient",
            "urgency": "standard",
        },
        "clinical_documents": [
            {
                "id": "doc-1",
                "title": "Orthopedic Consult Note",
                "doc_type": "consult",
                "date": "2026-06-20",
                "text": (
                    "Severe medial compartment narrowing on radiographs. "
                    "Completed 12 weeks of physical therapy and NSAIDs without relief. "
                    "Reports moderate to severe pain limiting ambulation."
                ),
            }
        ],
        "policy": policy or dict(SYNTHETIC_LCD),
        "sla_hours": 72,
        "expected_path": "approve",
        "criteria": [
            {
                "criterion_id": "C1",
                "criterion_text": "Moderate to severe radiographic findings of degenerative joint disease",
                "depth": 1,
                "logic": None,
            },
            {
                "criterion_id": "C2",
                "criterion_text": "Medical management has been tried and failed",
                "depth": 1,
                "logic": None,
            },
        ],
        "criteria_facts": criteria_facts,
    }


def make_request(scenario: dict, *, clinical_documents: list | None = None) -> PARequest:
    documents = scenario["clinical_documents"] if clinical_documents is None else clinical_documents
    return PARequest(
        id="PA-9001",
        scenario_id=scenario["id"],
        member=scenario["member"],
        provider=scenario["provider"],
        service=scenario["service"],
        clinical_documents=documents,
        processing_status="queued",
        determination_status="in_review",
        policy=scenario["policy"],
        sla_due_at="2026-07-08T00:00:00+00:00",
        created_at="2026-07-05T00:00:00+00:00",
        audit_trail=[],
    )


def test_bedrock_converse_payload_uses_sonnet_5_high_effort_defaults() -> None:
    payload = build_bedrock_converse_request(Settings(), "Review this prior auth case.")

    assert payload["modelId"] == "us.anthropic.claude-sonnet-5"
    assert payload["inferenceConfig"] == {"maxTokens": 8192}
    assert payload["additionalModelRequestFields"] == {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
    }
    assert payload["messages"][0]["content"][0]["text"] == "Review this prior auth case."


MET_FACT = {
    "status": "MET",
    "evidence": [
        {
            "quote": "Severe medial compartment narrowing on radiographs.",
            "source_document": "Orthopedic Consult Note",
            "document_date": "2026-06-20",
        }
    ],
    "rationale": "Radiographs document severe degenerative changes.",
    "confidence": 92,
}

MET_FACT_2 = {
    "status": "MET",
    "evidence": [
        {
            "quote": "Completed 12 weeks of physical therapy and NSAIDs without relief.",
            "source_document": "Orthopedic Consult Note",
            "document_date": "2026-06-20",
        }
    ],
    "rationale": "Conservative management documented and failed.",
    "confidence": 88,
}


@pytest.fixture
def settings() -> Settings:
    return Settings(mock_processing_seconds=0.0)


async def run_rubric(scenario: dict, settings: Settings, **kwargs) -> Determination:
    request = make_request(scenario, **kwargs)
    return await RubricEngine().evaluate(request, scenario, settings)


async def test_all_met_criteria_approve(settings) -> None:
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    determination = await run_rubric(scenario, settings)

    assert determination.recommendation == "approve"
    assert "deny" not in determination.recommendation
    assert determination.criteria_met == "2/2 required criteria met"
    assert determination.gaps == []
    first = determination.criteria_evaluations[0]
    assert first.evidence[0].quote == "Severe medial compartment narrowing on radiographs."
    assert first.evidence[0].source_document == "Orthopedic Consult Note"
    assert first.confidence == 92
    assert "LCD L99999" in determination.rationale
    assert determination.attribution.engine == "offline"
    assert determination.attribution.policy_source_type == "lcd"
    assert determination.attribution.policy_code == "LCD L99999"
    assert determination.attribution.policy_title == "Synthetic Test LCD"
    assert determination.attribution.policy_version == "1"
    assert determination.attribution.lcd_id == "L99999"
    assert determination.attribution.contractor == "Example MAC"
    assert determination.attribution.ncd_id is None
    assert determination.attribution.model_id is None
    # The synthetic LCD has no local file, so no coverage check is attached.
    assert determination.coverage_check is None


async def test_not_met_criterion_pends_with_gap(settings) -> None:
    not_met = {
        "status": "NOT_MET",
        "evidence": [],
        "rationale": "No conservative management documented.",
        "confidence": 75,
    }
    scenario = make_scenario({"C1": MET_FACT, "C2": not_met})
    determination = await run_rubric(scenario, settings)

    assert determination.recommendation == "pend"
    assert "deny" not in determination.recommendation
    assert determination.criteria_met == "1/2 required criteria met"
    assert "Medical management has been tried and failed" in determination.gaps


async def test_insufficient_criterion_pends(settings) -> None:
    insufficient = {
        "status": "INSUFFICIENT",
        "evidence": [],
        "rationale": "Imaging report not attached.",
        "confidence": 30,
    }
    scenario = make_scenario({"C1": insufficient, "C2": MET_FACT_2})
    determination = await run_rubric(scenario, settings)

    assert determination.recommendation == "pend"
    statuses = {e.criterion_id: e.status for e in determination.criteria_evaluations}
    assert statuses["C1"] == "INSUFFICIENT"


async def test_missing_fact_treated_as_insufficient(settings) -> None:
    scenario = make_scenario({"C1": MET_FACT})  # no fact for C2
    determination = await run_rubric(scenario, settings)

    assert determination.recommendation == "pend"
    missing = next(e for e in determination.criteria_evaluations if e.criterion_id == "C2")
    assert missing.status == "INSUFFICIENT"
    assert missing.rationale == "No documented evidence addresses this criterion."
    assert missing.confidence == 0


async def test_validation_gate_no_clinical_documents_pends(settings) -> None:
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    determination = await run_rubric(scenario, settings, clinical_documents=[])

    assert determination.recommendation == "pend"
    assert determination.criteria_evaluations == []
    assert any("clinical documentation" in gap.lower() for gap in determination.gaps)
    assert "deny" not in determination.recommendation


async def test_ncd_policy_attaches_coverage_check(settings) -> None:
    ncd_policy = {
        "source_type": "ncd",
        "code": "NCD 150.3",
        "title": "Bone (Mineral) Density Studies",
        "version": "2",
        "ncd_id": "150.3",
        "ncd_version": "2",
    }
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2}, policy=ncd_policy)
    determination = await run_rubric(scenario, settings)

    assert determination.coverage_check is not None
    assert determination.coverage_check.ncd_id == "150.3"
    assert determination.coverage_check.source_type == "ncd"
    assert determination.coverage_check.covered is True
    assert determination.attribution.ncd_id == "150.3"
    assert determination.attribution.policy_source_type == "ncd"
    assert "150.3" in determination.rationale


async def test_missing_coverage_file_tolerated(settings) -> None:
    ncd_policy = {
        "source_type": "ncd",
        "code": "NCD 999.9",
        "title": "Nonexistent NCD",
        "ncd_id": "999.9",
        "ncd_version": "1",
    }
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2}, policy=ncd_policy)
    determination = await run_rubric(scenario, settings)

    assert determination.coverage_check is None
    assert determination.recommendation == "approve"


class ExplodingEngine(Engine):
    id = "openai_gpt"
    label = "Stub OpenAI GPT"
    description = "Always raises for fallback testing."

    async def evaluate(self, request, scenario, settings):
        raise RuntimeError("kaboom")


class ExplodingClaudeEngine(Engine):
    id = "anthropic_claude"
    label = "Stub Anthropic Claude"
    description = "Always raises for fallback testing."

    async def evaluate(self, request, scenario, settings):
        raise RuntimeError("kaboom")


async def test_registry_falls_back_to_offline_when_engine_raises(settings) -> None:
    registry = EngineRegistry({"offline": RubricEngine(), "openai_gpt": ExplodingEngine()})
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    request = make_request(scenario)

    determination, notice = await registry.run("openai_gpt", request, scenario, settings)

    assert determination.attribution.engine == "offline"
    assert notice is not None
    assert "Stub OpenAI GPT unavailable — fell back to the rules engine" in notice
    assert "kaboom" in notice


def test_source_skill_prompt_includes_vendored_skill_context() -> None:
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    request = make_request(scenario)

    prompt = build_source_skill_prompt(request, scenario)

    assert prompt.startswith("You are Claude Code")
    assert "vendored Anthropic prior-auth-review skill" in prompt
    assert "references/rubric.md" in prompt
    assert "Default Policy: Lenient Mode" in prompt
    assert "Evaluate every criterion id exactly once" in prompt
    assert "C1: Moderate to severe radiographic findings" in prompt


def test_openai_source_skill_prompt_adapts_claude_skill_for_gpt() -> None:
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    request = make_request(scenario)

    prompt = build_openai_source_skill_prompt(request, scenario)

    assert prompt.startswith("You are OpenAI GPT")
    assert "source-skill files were written for Claude Code" in prompt
    assert "not as instructions about your identity" in prompt
    assert "Do not call tools, inspect files, use MCP servers" in prompt
    assert "references/rubric.md" in prompt
    assert "Default Policy: Lenient Mode" in prompt
    assert "You are Claude Code running" not in prompt


def test_llm_response_json_schema_is_strict_for_codex_structured_output() -> None:
    schema = llm_response_json_schema()
    criterion_schema = schema["properties"]["criteria"]["items"]
    evidence_schema = criterion_schema["properties"]["evidence"]["items"]

    assert schema["additionalProperties"] is False
    assert criterion_schema["additionalProperties"] is False
    assert evidence_schema["additionalProperties"] is False
    assert set(schema["required"]) == {"criteria", "recommendation", "rationale"}
    assert set(criterion_schema["required"]) == {
        "criterion_id",
        "status",
        "evidence",
        "rationale",
        "confidence",
    }
    assert set(evidence_schema["required"]) == {
        "quote",
        "source_document",
        "document_date",
    }


def test_source_skill_payload_requires_all_criteria_and_verbatim_quotes() -> None:
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    request = make_request(scenario)
    payload = {
        "criteria": [
            {
                "criterion_id": "C1",
                "status": "MET",
                "evidence": [
                    {
                        "quote": "Severe medial compartment narrowing on radiographs.",
                        "source_document": "Orthopedic Consult Note",
                        "document_date": "2026-06-20",
                    }
                ],
                "rationale": "Supported.",
                "confidence": 90,
            }
        ],
        "recommendation": "approve",
        "rationale": "All criteria met.",
    }

    with pytest.raises(ValueError, match="did not evaluate every criterion"):
        determination_from_payload(
            payload,
            request,
            scenario,
            engine="anthropic_claude",
            engine_label="Anthropic Claude",
            model_id="test-model",
            require_all_criteria=True,
            enforce_recommendation=True,
            validate_evidence_quotes=True,
        )

    payload["criteria"].append(
        {
            "criterion_id": "C2",
            "status": "MET",
            "evidence": [
                {
                    "quote": "This quote does not appear in the note.",
                    "source_document": "Orthopedic Consult Note",
                    "document_date": "2026-06-20",
                }
            ],
            "rationale": "Supported.",
            "confidence": 90,
        }
    )

    with pytest.raises(ValueError, match="not verbatim"):
        determination_from_payload(
            payload,
            request,
            scenario,
            engine="openai_gpt",
            engine_label="OpenAI GPT",
            model_id="test-model",
            require_all_criteria=True,
            enforce_recommendation=True,
            validate_evidence_quotes=True,
        )


def test_source_skill_payload_rejects_met_without_evidence() -> None:
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    request = make_request(scenario)
    payload = {
        "criteria": [
            {
                "criterion_id": "C1",
                "status": "MET",
                "evidence": [],
                "rationale": "Unsupported.",
                "confidence": 90,
            },
            {
                "criterion_id": "C2",
                "status": "MET",
                "evidence": [
                    {
                        "quote": "Completed 12 weeks of physical therapy and NSAIDs without relief.",
                        "source_document": "Orthopedic Consult Note",
                        "document_date": "2026-06-20",
                    }
                ],
                "rationale": "Supported.",
                "confidence": 90,
            },
        ],
        "recommendation": "approve",
        "rationale": "All criteria met.",
    }

    with pytest.raises(ValueError, match="MET without validated evidence"):
        determination_from_payload(
            payload,
            request,
            scenario,
            engine="openai_gpt",
            engine_label="OpenAI GPT",
            model_id="test-model",
            require_all_criteria=True,
            enforce_recommendation=True,
            validate_evidence_quotes=True,
            require_evidence_for_met=True,
        )


async def test_registry_falls_back_when_engine_disabled() -> None:
    disabled_settings = Settings(bedrock_enabled=False, mock_processing_seconds=0.0)
    registry = EngineRegistry(
        {"offline": RubricEngine(), "anthropic_claude": ExplodingClaudeEngine()}
    )
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    request = make_request(scenario)

    determination, notice = await registry.run(
        "anthropic_claude", request, scenario, disabled_settings
    )

    assert determination.attribution.engine == "offline"
    assert notice is not None
    assert "fell back to the rules engine" in notice


async def test_openai_gpt_uses_source_skill_prompt_and_reasoning_effort(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    request = make_request(scenario)
    captured: dict[str, object] = {}
    response_json = """
    {
      "criteria": [
        {
          "criterion_id": "C1",
          "status": "MET",
          "evidence": [
            {
              "quote": "Severe medial compartment narrowing on radiographs.",
              "source_document": "Orthopedic Consult Note",
              "document_date": "2026-06-20"
            }
          ],
          "rationale": "Supported.",
          "confidence": 90
        },
        {
          "criterion_id": "C2",
          "status": "MET",
          "evidence": [
            {
              "quote": "Completed 12 weeks of physical therapy and NSAIDs without relief.",
              "source_document": "Orthopedic Consult Note",
              "document_date": "2026-06-20"
            }
          ],
          "rationale": "Supported.",
          "confidence": 90
        }
      ],
      "recommendation": "approve",
      "rationale": "All criteria met."
    }
    """

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            output_path = captured["output_path"]
            assert isinstance(output_path, Path)
            output_path.write_text(response_json, encoding="utf-8")
            return (b"codex progress that is not json", b"")

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        schema_path = Path(args[args.index("--output-schema") + 1])
        output_path = Path(args[args.index("--output-last-message") + 1])
        captured["schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
        captured["output_path"] = output_path
        return FakeProcess()

    monkeypatch.setattr(
        "backend.app.engines.codex.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    determination = await CodexEngine().evaluate(request, scenario, settings)

    args = captured["args"]
    assert isinstance(args, tuple)
    assert args[:2] == ("codex", "exec")
    assert "--skip-git-repo-check" in args
    assert "--ephemeral" in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert "--ask-for-approval" not in args
    assert Path(args[args.index("--output-schema") + 1]).name == "response-schema.json"
    assert Path(args[args.index("--output-last-message") + 1]).name == "final-message.json"
    assert args[args.index("-m") + 1] == "gpt-5.5"
    assert args[args.index("-c") + 1] == 'model_reasoning_effort="xhigh"'
    assert captured["schema"] == llm_response_json_schema()
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    output_path = captured["output_path"]
    assert isinstance(output_path, Path)
    assert kwargs["cwd"] == str(output_path.parent)
    assert kwargs["stdin"] == asyncio.subprocess.DEVNULL
    prompt = args[-1]
    assert isinstance(prompt, str)
    assert prompt.startswith("You are OpenAI GPT")
    assert "source-skill files were written for Claude Code" in prompt
    assert "You are Claude Code running" not in prompt
    assert "references/rubric.md" in prompt
    assert determination.attribution.engine == "openai_gpt"


# --- Bedrock credentials --------------------------------------------------------


class _FakeBedrockClient:
    def converse(self, **kwargs):
        return {"output": {"message": {"content": [{"text": "{}"}]}}}


def _capture_boto3_sessions(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    import boto3

    calls: list[dict] = []

    class FakeSession:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def client(self, service_name, region_name=None):
            assert service_name == "bedrock-runtime"
            return _FakeBedrockClient()

    monkeypatch.setattr(boto3, "Session", FakeSession)
    return calls


def test_bedrock_default_uses_standard_credential_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PA_EXPRESS_AWS_PROFILE", raising=False)
    monkeypatch.delenv("PA_EXPRESS_BEDROCK_AUTH_METHOD", raising=False)
    settings = Settings()
    assert settings.aws_profile == ""
    assert settings.bedrock_auth_method == "profile"

    calls = _capture_boto3_sessions(monkeypatch)
    invocation = invoke_bedrock_converse(settings, "Review this prior auth case.")

    assert calls == [{}]
    assert invocation.response_text == "{}"


def test_bedrock_named_profile_is_used_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_boto3_sessions(monkeypatch)
    invoke_bedrock_converse(Settings(aws_profile="team-profile"), "Review.")

    assert calls == [{"profile_name": "team-profile"}]


# --- Policy ids, letter lines, and the local coverage directory ------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("150.3", ("ncd", "150.3")),
        ("150-3", ("ncd", "150.3")),
        ("NCD 150.3", ("ncd", "150.3")),
        ("ncd-150-3", ("ncd", "150.3")),
        ("20.32", ("ncd", "20.32")),
        ("L12345", ("lcd", "L12345")),
        ("l12345", ("lcd", "L12345")),
        ("LCD L12345", ("lcd", "L12345")),
        ("lcd-l12345", ("lcd", "L12345")),
        ("LCD 12345", ("lcd", "L12345")),
    ],
)
def test_normalize_policy_id_accepts_common_forms(value: str, expected: tuple[str, str]) -> None:
    key = normalize_policy_id(value)
    assert key is not None
    assert (key.source_type, key.policy_id) == expected


@pytest.mark.parametrize("value", ["", "   ", "nope", "NCD L12345", "LCD 150.3", "ncd-"])
def test_normalize_policy_id_rejects_other_values(value: str) -> None:
    assert normalize_policy_id(value) is None


def test_letter_policy_line_ncd_form() -> None:
    attribution = Attribution(
        engine="offline",
        engine_label="Rules engine",
        policy_source_type="ncd",
        policy_code="NCD 150.3",
        policy_title="Bone (Mineral) Density Studies",
        policy_version="2",
        ncd_id="150.3",
        ncd_version="2",
        evaluated_at="2026-07-05T00:00:00+00:00",
    )
    assert letter_policy_line(attribution) == "Coverage Policy: Medicare NCD 150.3 (Version 2)"


def test_letter_policy_line_lcd_form() -> None:
    attribution = Attribution(
        engine="offline",
        engine_label="Rules engine",
        policy_source_type="lcd",
        policy_code="LCD L12345",
        policy_title="Example Procedure",
        policy_version="7",
        lcd_id="L12345",
        contractor="Example MAC",
        evaluated_at="2026-07-05T00:00:00+00:00",
    )
    assert (
        letter_policy_line(attribution)
        == "Coverage Policy: Medicare LCD L12345 — Example Procedure (Example MAC)"
    )


def test_new_lcd_file_is_found_without_code_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(coverage_module, "COVERAGE_DIR", tmp_path)
    with pytest.raises(AppError) as missing:
        load_coverage_check("L99999")
    assert missing.value.code == "COVERAGE_NOT_FOUND"

    (tmp_path / "lcd-l99999.json").write_text(
        json.dumps(
            {
                "lcd_id": "L99999",
                "title": "Synthetic Test LCD",
                "document_version": "4",
                "revision_effective_date": "2026-01-01",
                "contractor": {"name": "Example MAC"},
                "covered_indication_summary": "Covered when every criterion is met.",
                "source": {"mcd_url": "https://example.test/lcd/L99999"},
                "criteria": [{"id": "C1", "text": "A documented indication."}],
                "full_text": {"coverage_indications": "First paragraph.\n\nSecond paragraph."},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "lcd-broken.json").write_text("{ not json", encoding="utf-8")

    check = load_coverage_check("LCD L99999")
    assert check.policy_id == "L99999"
    assert check.source_type == "lcd"
    assert check.lcd_id == "L99999"
    assert check.ncd_id is None
    assert check.version == "4"
    assert check.contractor == "Example MAC"
    assert check.source_url == "https://example.test/lcd/L99999"

    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    document = load_policy_document("lcd-l99999", [scenario])
    assert document.local_file_available is True
    assert document.code == "LCD L99999"
    assert document.contractor == "Example MAC"
    assert document.effective_date == "2026-01-01"
    assert [criterion.text for criterion in document.criteria] == ["A documented indication."]
    assert document.sections[0].paragraphs == ["First paragraph.", "Second paragraph."]
    assert document.review_criteria[0].scenario_id == scenario["id"]


async def test_lcd_scenario_attaches_coverage_check_from_file(
    settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(coverage_module, "COVERAGE_DIR", tmp_path)
    (tmp_path / "lcd-l99999.json").write_text(
        json.dumps({"lcd_id": "L99999", "title": "Synthetic Test LCD", "version": "1"}),
        encoding="utf-8",
    )
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    determination = await run_rubric(scenario, settings)

    assert determination.coverage_check is not None
    assert determination.coverage_check.lcd_id == "L99999"
    assert determination.recommendation == "approve"


async def test_missing_coverage_directory_is_tolerated(
    settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(coverage_module, "COVERAGE_DIR", tmp_path / "does-not-exist")
    scenario = make_scenario({"C1": MET_FACT, "C2": MET_FACT_2})
    determination = await run_rubric(scenario, settings)

    assert determination.coverage_check is None
    assert determination.recommendation == "approve"

    # The policy document still resolves from the scenario that cites it.
    document = load_policy_document("L99999", [scenario])
    assert document.local_file_available is False
    assert document.source_type == "lcd"
    assert document.title == "Synthetic Test LCD"
    assert document.review_criteria[0].criteria[0].criterion_id == "C1"

    with pytest.raises(AppError) as unknown:
        load_policy_document("L00000", [scenario])
    assert unknown.value.status_code == 404
    assert unknown.value.code == "POLICY_NOT_FOUND"
