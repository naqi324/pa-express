"""Offline engine — deterministic port of the Anthropic prior-auth-review lenient rubric.

Recommendation is only ever "approve" or "pend"; the rubric never denies.
"""

import asyncio
from datetime import datetime, timezone

from ..config import Settings
from ..errors import AppError
from ..schemas import (
    Attribution,
    CoverageCheck,
    CriterionEvaluation,
    Determination,
    EvidenceCitation,
    PARequest,
)
from ..services.coverage import load_coverage_check
from ..services.policies import attribution_policy_fields, policy_key, policy_label
from .base import RubricEngineBase

_MISSING_FACT_RATIONALE = "No documented evidence addresses this criterion."


def _validation_gaps(request: PARequest) -> list[str]:
    gaps: list[str] = []
    if not request.member.name or not request.member.member_id:
        gaps.append("Member identification is incomplete; request corrected member information.")
    if not request.provider.name or not request.provider.npi:
        gaps.append("Provider identification (name/NPI) is incomplete; request provider credentialing documentation.")
    if not request.service.description or not request.service.cpt_codes:
        gaps.append("The requested service or its CPT/HCPCS codes are missing; request a corrected submission.")
    if not request.clinical_documents:
        gaps.append("No clinical documentation was submitted; request supporting clinical records.")
    return gaps


class RubricEngine(RubricEngineBase):
    async def evaluate(
        self,
        request: PARequest,
        scenario: dict,
        settings: Settings,
    ) -> Determination:
        await asyncio.sleep(settings.mock_processing_seconds)

        policy = scenario.get("policy") or {}
        label = policy_label(policy)
        attribution = Attribution(
            engine="offline",
            engine_label=self.label,
            model_id=None,
            **attribution_policy_fields(policy),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

        coverage_check: CoverageCheck | None = None
        key = policy_key(policy)
        if key is not None:
            try:
                coverage_check = load_coverage_check(f"{key.source_type} {key.policy_id}")
            except AppError:
                coverage_check = None

        gate_gaps = _validation_gaps(request)
        if gate_gaps:
            return Determination(
                id="",
                request_id=request.id,
                recommendation="pend",
                rationale=(
                    f"Intake validation against {label} could not be completed because required "
                    "elements of the request are missing. Per the lenient rubric the case is pended so the "
                    "submitter can supply the missing information rather than facing an adverse decision."
                ),
                criteria_evaluations=[],
                criteria_met="0/0 required criteria met",
                gaps=gate_gaps,
                coverage_check=coverage_check,
                attribution=attribution,
            )

        criteria: list[dict] = scenario.get("criteria") or []
        criteria_facts: dict = scenario.get("criteria_facts") or {}

        evaluations: list[CriterionEvaluation] = []
        for criterion in criteria:
            criterion_id = str(criterion.get("criterion_id", ""))
            fact = criteria_facts.get(criterion_id)
            if fact is None:
                evaluations.append(
                    CriterionEvaluation(
                        criterion_id=criterion_id,
                        criterion_text=str(criterion.get("criterion_text", "")),
                        depth=int(criterion.get("depth", 0)),
                        logic=criterion.get("logic"),
                        status="INSUFFICIENT",
                        evidence=[],
                        rationale=_MISSING_FACT_RATIONALE,
                        confidence=0,
                    )
                )
                continue
            evaluations.append(
                CriterionEvaluation(
                    criterion_id=criterion_id,
                    criterion_text=str(criterion.get("criterion_text", "")),
                    depth=int(criterion.get("depth", 0)),
                    logic=criterion.get("logic"),
                    status=fact.get("status", "INSUFFICIENT"),
                    evidence=[
                        EvidenceCitation(
                            quote=str(item.get("quote", "")),
                            source_document=str(item.get("source_document", "")),
                            document_date=item.get("document_date"),
                        )
                        for item in fact.get("evidence") or []
                    ],
                    rationale=str(fact.get("rationale", "")),
                    confidence=int(fact.get("confidence", 0)),
                )
            )

        met_count = sum(1 for evaluation in evaluations if evaluation.status == "MET")
        total = len(evaluations)
        all_met = total > 0 and met_count == total
        gaps = [
            evaluation.criterion_text
            for evaluation in evaluations
            if evaluation.status != "MET"
        ]

        if all_met:
            rationale = (
                f"All {total} required criteria under {label} are met with documented clinical "
                "evidence. The submitted records support medical necessity for the requested service. "
                "The rubric recommends approval, subject to human reviewer disposition."
            )
            recommendation = "approve"
        else:
            rationale = (
                f"{met_count} of {total} required criteria under {label} are met. "
                "The remaining criteria lack sufficient documented evidence, so the lenient rubric "
                "recommends pending the case to request the specific missing documentation."
            )
            recommendation = "pend"

        return Determination(
            id="",
            request_id=request.id,
            recommendation=recommendation,
            rationale=rationale,
            criteria_evaluations=evaluations,
            criteria_met=f"{met_count}/{total} required criteria met",
            gaps=gaps,
            coverage_check=coverage_check,
            attribution=attribution,
        )
