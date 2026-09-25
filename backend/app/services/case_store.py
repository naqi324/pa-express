"""Session-scoped in-memory store for PA requests, evaluations, and determinations."""

import asyncio
from datetime import datetime, timedelta, timezone

from ..errors import AppError
from ..schemas import (
    AuditEvent,
    Determination,
    EvaluationStatus,
    HumanActionRequest,
    Letter,
    LlmInspection,
    PARequest,
    PARequestSummary,
)

_ACTION_TO_STATE: dict[str, str] = {
    "approve": "approved",
    "pend": "pended",
    "refer_md": "referred_md",
}

# CMS-0057-F decision clocks: expedited <=72 hours, standard <=7 calendar days.
_SLA_HOURS_EXPEDITED = 72
_SLA_HOURS_STANDARD = 7 * 24

_APPROVAL_VALIDITY_DAYS = 90
_SERVER_REVIEWER_ACTOR = "UM Reviewer"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CaseStore:
    """Per-session storage of PA requests keyed by id, plus evaluations and determinations."""

    def __init__(self) -> None:
        self._requests: dict[str, PARequest] = {}
        self._evaluations: dict[str, EvaluationStatus] = {}
        self._determinations: dict[str, Determination] = {}
        self._llm_inspections: dict[str, LlmInspection] = {}
        self._letters: dict[str, Letter] = {}
        self._next_request_number = 1001
        self._next_eval_number = 1
        self._lock = asyncio.Lock()

    async def create_from_scenario(self, scenario: dict) -> PARequest:
        async with self._lock:
            request_id = f"PA-{self._next_request_number}"
            self._next_request_number += 1

            now = datetime.now(timezone.utc)
            urgency = str(scenario.get("service", {}).get("urgency", "standard"))
            sla_hours = (
                _SLA_HOURS_EXPEDITED if urgency == "expedited" else _SLA_HOURS_STANDARD
            )
            sla_due_at = now + timedelta(hours=sla_hours)

            request = PARequest(
                id=request_id,
                scenario_id=scenario.get("id"),
                member=scenario["member"],
                provider=scenario["provider"],
                service=scenario["service"],
                clinical_documents=scenario.get("clinical_documents", []),
                processing_status="queued",
                determination_status="in_review",
                policy=scenario.get("policy"),
                sla_due_at=sla_due_at.isoformat(),
                created_at=now.isoformat(),
                audit_trail=[
                    AuditEvent(
                        timestamp=now.isoformat(),
                        actor="Intake Automation",
                        event="request_created",
                        from_state=None,
                        to_state="queued",
                    )
                ],
                scenario_hint=scenario.get("summary_subtitle") or scenario.get("scenario_hint"),
            )
            self._requests[request_id] = request
            return request

    def get(self, request_id: str) -> PARequest:
        request = self._requests.get(request_id)
        if request is None:
            raise AppError(
                404,
                "REQUEST_NOT_FOUND",
                f"Prior auth request {request_id} was not found in this session.",
                "Create a request from a scenario first.",
            )
        return request

    def loaded_scenario_ids(self) -> set[str]:
        """Scenario ids already instantiated in this session (for idempotent seeding)."""
        return {
            request.scenario_id
            for request in self._requests.values()
            if request.scenario_id
        }

    def list_summaries(self) -> list[PARequestSummary]:
        summaries = [
            PARequestSummary(
                id=request.id,
                scenario_id=request.scenario_id,
                member_name=request.member.name,
                service_description=request.service.description,
                cpt_codes=request.service.cpt_codes,
                plan_type=request.member.plan_type,
                urgency=request.service.urgency,
                processing_status=request.processing_status,
                determination_status=request.determination_status,
                recommendation=(
                    determination.recommendation
                    if (determination := self._determinations.get(request.id))
                    else None
                ),
                sla_due_at=request.sla_due_at,
                created_at=request.created_at,
                notified_at=request.notified_at,
            )
            for request in self._requests.values()
        ]
        # Worklist order: expedited first, then closest SLA deadline.
        summaries.sort(
            key=lambda summary: (summary.urgency != "expedited", summary.sla_due_at)
        )
        return summaries

    async def create_evaluation(self, request_id: str, engine: str) -> EvaluationStatus:
        request = self.get(request_id)
        async with self._lock:
            eval_id = f"EV-{self._next_eval_number}"
            self._next_eval_number += 1
            evaluation = EvaluationStatus(
                id=eval_id,
                request_id=request.id,
                status="queued",
                engine=engine,  # type: ignore[arg-type]
                determination=None,
                error=None,
            )
            self._evaluations[eval_id] = evaluation
            # A (re-)run returns the case to review state and voids any prior disposition.
            request.latest_eval_id = eval_id
            request.processing_status = "queued"
            request.determination_status = "in_review"
            self._llm_inspections.pop(request_id, None)
            request.auth_valid_from = None
            request.auth_valid_through = None
            request.requested_items = []
            request.md_summary = None
            request.notified_at = None
            return evaluation

    def get_evaluation(self, request_id: str, eval_id: str) -> EvaluationStatus:
        evaluation = self._evaluations.get(eval_id)
        if evaluation is None or evaluation.request_id != request_id:
            raise AppError(
                404,
                "EVALUATION_NOT_FOUND",
                f"Evaluation {eval_id} was not found for request {request_id}.",
                "Start an evaluation before polling for its status.",
            )
        return evaluation

    def get_determination(self, request_id: str) -> Determination:
        self.get(request_id)
        determination = self._determinations.get(request_id)
        if determination is None:
            raise AppError(
                404,
                "DETERMINATION_NOT_READY",
                f"No completed determination is available for request {request_id}.",
                "Run an evaluation to completion first.",
            )
        return determination

    def latest_determination(self, request_id: str) -> Determination | None:
        return self._determinations.get(request_id)

    def set_determination(self, request_id: str, determination: Determination) -> None:
        self._determinations[request_id] = determination
        # A re-run invalidates any previously composed letter draft.
        self._letters.pop(request_id, None)

    def set_llm_inspection(self, request_id: str, inspection: LlmInspection) -> None:
        self._llm_inspections[request_id] = inspection

    def get_llm_inspection(self, request_id: str) -> LlmInspection:
        self.get(request_id)
        inspection = self._llm_inspections.get(request_id)
        if inspection is None:
            raise AppError(
                404,
                "LLM_INSPECTION_NOT_READY",
                f"No LLM inspection record is available for request {request_id}.",
                "Wait for the evaluation to complete, then open the recommendation inspector.",
            )
        return inspection

    def get_letter(self, request_id: str) -> Letter | None:
        return self._letters.get(request_id)

    def set_letter(self, request_id: str, letter: Letter) -> None:
        self._letters[request_id] = letter

    def update_letter(self, request_id: str, body: str, mark_ready: bool) -> Letter:
        request = self.get(request_id)
        letter = self._letters.get(request_id)
        if letter is None:
            raise AppError(
                404,
                "LETTER_NOT_READY",
                f"No letter draft exists for request {request_id}.",
                "Load the letter after recording a disposition, then save or send it.",
            )
        if letter.status == "ready":
            raise AppError(
                409,
                "LETTER_ALREADY_FINALIZED",
                f"The provider letter for request {request_id} has already been finalized.",
                "Create a fresh evaluation or amendment workflow before changing the notice.",
            )
        edited = body != letter.body
        letter.body = body
        if edited:
            self.add_audit_event(
                request_id, "letter_edited", "UM Reviewer",
                from_state=letter.status, to_state=letter.status,
            )
        if mark_ready:
            letter.status = "ready"
            request.notified_at = _now_iso()
            self.add_audit_event(
                request_id, "letter_sent", "UM Reviewer",
                from_state="draft", to_state="ready",
            )
        return letter

    def add_audit_event(
        self,
        request_id: str,
        event: str,
        actor: str,
        from_state: str | None = None,
        to_state: str | None = None,
    ) -> AuditEvent:
        request = self.get(request_id)
        audit_event = AuditEvent(
            timestamp=_now_iso(),
            actor=actor,
            event=event,
            from_state=from_state,
            to_state=to_state,
        )
        request.audit_trail.append(audit_event)
        return audit_event

    def set_processing_status(self, request_id: str, status: str) -> None:
        request = self.get(request_id)
        request.processing_status = status  # type: ignore[assignment]

    async def apply_action(self, request_id: str, action: HumanActionRequest) -> PARequest:
        async with self._lock:
            request = self.get(request_id)
            determination = self._determinations.get(request_id)
            if determination is None or request.processing_status != "completed":
                raise AppError(
                    409,
                    "ACTION_NOT_ALLOWED",
                    "A completed determination is required before a human disposition.",
                    "Run an evaluation to completion, then apply the action.",
                )
            if request.determination_status != "in_review":
                raise AppError(
                    409,
                    "ALREADY_DISPOSED",
                    f"Request {request_id} already has a recorded disposition.",
                    "Re-run the determination to review the case again.",
                )
            if action.action == "pend" and not action.requested_items:
                raise AppError(
                    422,
                    "PEND_ITEMS_REQUIRED",
                    "A pend must name the specific information requested from the provider.",
                    "Select at least one missing item before pending the request.",
                )
            if action.action == "refer_md" and not action.note.strip():
                raise AppError(
                    422,
                    "MD_SUMMARY_REQUIRED",
                    "A referral to the Medical Director requires the reviewer's summary.",
                    "Add a summary and recommendation for the Medical Director.",
                )

            if action.action == "approve":
                now = datetime.now(timezone.utc)
                request.auth_valid_from = action.valid_from or now.date().isoformat()
                request.auth_valid_through = action.valid_through or (
                    now + timedelta(days=_APPROVAL_VALIDITY_DAYS)
                ).date().isoformat()
            elif action.action == "pend":
                request.requested_items = action.requested_items
            elif action.action == "refer_md":
                request.md_summary = action.note.strip()

            to_state = _ACTION_TO_STATE[action.action]
            from_state = request.determination_status
            request.determination_status = to_state  # type: ignore[assignment]
            event_name = f"human_action_{action.action}"
            if action.note:
                event_name = f"{event_name}: {action.note}"
            audit_event = AuditEvent(
                timestamp=_now_iso(),
                actor=_SERVER_REVIEWER_ACTOR,
                event=event_name,
                from_state=from_state,
                to_state=to_state,
            )
            request.audit_trail.append(audit_event)
            return request
