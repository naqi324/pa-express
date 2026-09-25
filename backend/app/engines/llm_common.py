"""Shared prompt construction and strict-JSON parsing for LLM-backed engines."""

import json
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path

from ..schemas import (
    Attribution,
    CriterionEvaluation,
    Determination,
    EngineId,
    EvidenceCitation,
    PARequest,
)
from ..services.policies import attribution_policy_fields

_JSON_CONTRACT = """{
  "criteria": [
    {
      "criterion_id": "...",
      "status": "MET|NOT_MET|INSUFFICIENT",
      "evidence": [{"quote": "...", "source_document": "...", "document_date": "..."}],
      "rationale": "...",
      "confidence": 0
    }
  ],
  "recommendation": "approve|pend",
  "rationale": "..."
}"""

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SOURCE_SKILL_DIR = _PROJECT_ROOT / "vendor" / "anthropic-prior-auth-review"
_SOURCE_SKILL_FILES = (
    "README.md",
    "SKILL.md",
    "references/rubric.md",
    "references/01-intake-assessment.md",
)

LLM_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["MET", "NOT_MET", "INSUFFICIENT"],
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "quote": {"type": "string"},
                                "source_document": {"type": "string"},
                                "document_date": {"type": ["string", "null"]},
                            },
                            "required": ["quote", "source_document", "document_date"],
                            "additionalProperties": False,
                        },
                    },
                    "rationale": {"type": "string"},
                    "confidence": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": [
                    "criterion_id",
                    "status",
                    "evidence",
                    "rationale",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "recommendation": {"type": "string", "enum": ["approve", "pend"]},
        "rationale": {"type": "string"},
    },
    "required": ["criteria", "recommendation", "rationale"],
    "additionalProperties": False,
}


def build_prompt(request: PARequest, scenario: dict) -> str:
    policy = scenario.get("policy") or {}
    criteria_lines = []
    for criterion in scenario.get("criteria") or []:
        logic = criterion.get("logic")
        logic_suffix = f" [logic: {logic}]" if logic else ""
        criteria_lines.append(
            f"- {criterion.get('criterion_id')}: {criterion.get('criterion_text')}{logic_suffix}"
        )
    document_blocks = []
    for document in request.clinical_documents:
        document_blocks.append(
            f"### {document.title} ({document.doc_type}, {document.date})\n{document.text}"
        )

    return (
        "You are a utilization-management clinical criteria reviewer performing a prior "
        "authorization evaluation.\n\n"
        f"Policy reference: {json.dumps(policy)}\n\n"
        f"Requested service: {request.service.description} "
        f"(CPT {', '.join(request.service.cpt_codes)}; ICD-10 {', '.join(request.service.icd10_codes)})\n\n"
        "Criteria to evaluate (evaluate every criterion by id):\n"
        + "\n".join(criteria_lines)
        + "\n\nClinical documentation:\n\n"
        + "\n\n".join(document_blocks)
        + "\n\nRespond with STRICT JSON only — no prose, no markdown fences — exactly this shape:\n"
        + _JSON_CONTRACT
        + "\n\nRules:\n"
        "- status must be one of MET, NOT_MET, INSUFFICIENT.\n"
        "- recommendation must be 'approve' only when every criterion is MET; otherwise 'pend'. "
        "You may NEVER recommend denial.\n"
        "- Every evidence quote must be copied VERBATIM from the clinical documentation above, "
        "with source_document set to the document title.\n"
        "- confidence is an integer 0-100.\n"
    )


@lru_cache(maxsize=1)
def load_source_skill_context() -> str:
    """Load the vendored Anthropic PA skill context used by the source-skill engine."""
    sections: list[str] = []
    for relative_path in _SOURCE_SKILL_FILES:
        path = _SOURCE_SKILL_DIR / relative_path
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            sections.append(f"## {relative_path}\n{text}")
    if not sections:
        raise FileNotFoundError(
            f"No source skill files were readable under {_SOURCE_SKILL_DIR}"
        )
    return "\n\n".join(sections)


def build_source_skill_prompt(request: PARequest, scenario: dict) -> str:
    """Prompt Claude as the vendored prior-auth-review skill, adapted to this app.

    The original skill expects Claude Code to orchestrate document extraction and MCP
    calls. This app has already structured the request, policy, criteria, and documents,
    so the engine asks Claude to perform the same clinical evidence mapping and lenient
    rubric application without calling external tools.
    """
    source_context = load_source_skill_context()
    return (
        "You are Claude Code running the vendored Anthropic prior-auth-review skill for "
        "a payer-side prior authorization review.\n\n"
        "Adaptation for this app:\n"
        "- The app has already collected the PA request, clinical documents, policy "
        "reference, and criteria list.\n"
        "- Do not call tools or ask follow-up questions. Use only the data below.\n"
        "- Apply the source skill's default lenient rubric: approve only when every "
        "required criterion is MET; otherwise pend for specific missing documentation.\n"
        "- You may NEVER recommend denial.\n"
        "- Evaluate every criterion id exactly once.\n"
        "- Every evidence quote must be copied verbatim from the clinical documentation "
        "and source_document must match the document title.\n"
        "- Return STRICT JSON only; no prose and no markdown fences.\n\n"
        "<source_skill_context>\n"
        f"{source_context}\n"
        "</source_skill_context>\n\n"
        + build_prompt(request, scenario)
    )


def build_openai_source_skill_prompt(request: PARequest, scenario: dict) -> str:
    """Prompt OpenAI GPT to apply the vendored Claude skill as source material."""
    source_context = load_source_skill_context()
    return (
        "You are OpenAI GPT acting as a utilization-management clinical criteria "
        "reviewer for a payer-side prior authorization review.\n\n"
        "The enclosed source-skill files were written for Claude Code. Treat them as "
        "reference material for the clinical evidence-mapping workflow and lenient "
        "prior-auth rubric, not as instructions about your identity, available tools, "
        "MCP servers, filesystem access, or execution environment.\n\n"
        "Adaptation for this app:\n"
        "- The app has already collected the PA request, clinical documents, policy "
        "reference, and criteria list.\n"
        "- Do not call tools, inspect files, use MCP servers, or ask follow-up "
        "questions. Use only the data below.\n"
        "- Ignore any source-skill instruction that depends on Claude Code tooling, "
        "MCP retrieval, shell access, or human-in-the-loop intake.\n"
        "- Apply the source skill's default lenient rubric: approve only when every "
        "required criterion is MET; otherwise pend for specific missing documentation.\n"
        "- You may NEVER recommend denial.\n"
        "- Evaluate every criterion id exactly once.\n"
        "- Every evidence quote must be copied verbatim from the clinical documentation "
        "and source_document must match the document title.\n"
        "- Return STRICT JSON only; no prose and no markdown fences.\n\n"
        "<source_skill_context>\n"
        f"{source_context}\n"
        "</source_skill_context>\n\n"
        + build_prompt(request, scenario)
    )


def llm_response_json_schema() -> dict:
    """Return a copy of the strict JSON schema expected from LLM engines."""
    return json.loads(json.dumps(LLM_RESPONSE_JSON_SCHEMA))


def parse_llm_json(raw_text: str) -> dict:
    """Defensively extract the JSON object from an LLM response."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Engine response did not contain a JSON object.")
    return json.loads(text[start : end + 1])


def determination_from_payload(
    payload: dict,
    request: PARequest,
    scenario: dict,
    *,
    engine: EngineId,
    engine_label: str,
    model_id: str | None,
    require_all_criteria: bool = False,
    enforce_recommendation: bool = False,
    validate_evidence_quotes: bool = False,
    require_evidence_for_met: bool = False,
) -> Determination:
    policy = scenario.get("policy") or {}
    criteria_by_id = {
        str(criterion.get("criterion_id")): criterion
        for criterion in scenario.get("criteria") or []
    }

    raw_criteria = payload.get("criteria")
    if not isinstance(raw_criteria, list):
        raise ValueError("Engine response is missing the criteria array.")

    evaluations: list[CriterionEvaluation] = []
    seen_ids: set[str] = set()
    documents_by_title = {document.title: document for document in request.clinical_documents}
    for entry in raw_criteria:
        if not isinstance(entry, dict):
            raise ValueError("Engine response contained a malformed criterion entry.")
        criterion_id = str(entry.get("criterion_id", ""))
        if require_all_criteria and criterion_id in seen_ids:
            raise ValueError(
                f"Engine response evaluated criterion {criterion_id!r} more than once."
            )
        seen_ids.add(criterion_id)
        authored = criteria_by_id.get(criterion_id, {})
        status = entry.get("status")
        if status not in {"MET", "NOT_MET", "INSUFFICIENT"}:
            raise ValueError(f"Invalid criterion status: {status!r}")
        evidence = [
            EvidenceCitation(
                quote=str(item.get("quote", "")),
                source_document=str(item.get("source_document", "")),
                document_date=item.get("document_date"),
            )
            for item in entry.get("evidence") or []
            if isinstance(item, dict)
        ]
        if validate_evidence_quotes:
            for citation in evidence:
                document = documents_by_title.get(citation.source_document)
                if document is None or citation.quote not in document.text:
                    raise ValueError(
                        "Engine response included an evidence quote that was not "
                        f"verbatim in source document {citation.source_document!r}."
                    )
        if require_evidence_for_met and status == "MET" and not evidence:
            raise ValueError(
                f"Engine response marked criterion {criterion_id!r} as MET without "
                "validated evidence."
            )
        confidence_raw = entry.get("confidence", 0)
        try:
            confidence = max(0, min(100, int(confidence_raw)))
        except (TypeError, ValueError):
            confidence = 0
        evaluations.append(
            CriterionEvaluation(
                criterion_id=criterion_id,
                criterion_text=str(authored.get("criterion_text", criterion_id)),
                depth=int(authored.get("depth", 0)),
                logic=authored.get("logic"),
                status=status,
                evidence=evidence,
                rationale=str(entry.get("rationale", "")),
                confidence=confidence,
            )
        )

    if require_all_criteria:
        expected_ids = set(criteria_by_id)
        missing = expected_ids - seen_ids
        extra = seen_ids - expected_ids
        if missing:
            raise ValueError(
                "Engine response did not evaluate every criterion: "
                + ", ".join(sorted(missing))
            )
        if extra:
            raise ValueError(
                "Engine response evaluated unknown criteria: "
                + ", ".join(sorted(extra))
            )

    recommendation = payload.get("recommendation")
    if recommendation not in {"approve", "pend"}:
        raise ValueError(f"Invalid recommendation: {recommendation!r}")

    met_count = sum(1 for evaluation in evaluations if evaluation.status == "MET")
    total = len(evaluations)
    if enforce_recommendation:
        expected_recommendation = "approve" if total > 0 and met_count == total else "pend"
        if recommendation != expected_recommendation:
            raise ValueError(
                "Engine response recommendation does not match the lenient rubric: "
                f"expected {expected_recommendation!r}, got {recommendation!r}."
            )
    gaps = [
        evaluation.criterion_text
        for evaluation in evaluations
        if evaluation.status != "MET"
    ]

    return Determination(
        id="",
        request_id=request.id,
        recommendation=recommendation,
        rationale=str(payload.get("rationale", "")),
        criteria_evaluations=evaluations,
        criteria_met=f"{met_count}/{total} required criteria met",
        gaps=gaps,
        coverage_check=None,
        attribution=Attribution(
            engine=engine,
            engine_label=engine_label,
            model_id=model_id,
            **attribution_policy_fields(policy),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
