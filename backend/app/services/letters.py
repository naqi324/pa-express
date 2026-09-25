"""Provider notification letter composition, modeled on the vendored letter templates."""

from datetime import datetime, timedelta, timezone

from ..errors import AppError
from ..schemas import Determination, Letter, PARequest
from .policies import letter_policy_line

_STATUS_LABELS = {
    "approved": "Approved",
    "pended": "Pended - Additional Information Requested",
}

# Providers get 45 calendar days to supply the requested documentation.
_PEND_RESPONSE_DAYS = 45


def _policy_lines(determination: Determination) -> list[str]:
    return [letter_policy_line(determination.attribution)]


def compose_letter(
    request: PARequest,
    determination: Determination,
    determination_status: str,
) -> Letter:
    if determination_status == "in_review":
        raise AppError(
            404,
            "LETTER_NOT_READY",
            "A notification letter is not available until a human disposition is recorded.",
            "Apply a reviewer action (approve or pend) first.",
        )
    if determination_status == "referred_md":
        raise AppError(
            409,
            "NO_LETTER_FOR_REFERRAL",
            "A Medical Director referral is an internal handoff; no provider letter is "
            "composed until the Medical Director records a determination.",
            "The provider is notified after the Medical Director completes their review.",
        )

    letter_type = "approval" if determination_status == "approved" else "pend"
    now = datetime.now(timezone.utc)
    status_label = _STATUS_LABELS.get(determination_status, determination_status)

    subject = (
        f"Prior Authorization {status_label}: {request.service.description} "
        f"for {request.member.name} ({request.id})"
    )

    lines: list[str] = [
        f"Date: {now.strftime('%m/%d/%Y')}",
        "",
        f"Provider: {request.provider.name}",
        f"Provider NPI: {request.provider.npi}",
        f"Organization: {request.provider.organization}",
        "",
        f"Member: {request.member.name}",
        f"Member ID: {request.member.member_id}",
        f"Date of Birth: {request.member.date_of_birth}",
        f"Plan: {request.member.plan_name}",
        "",
        f"Re: Prior Authorization Request {request.id}",
        f"Requested Service: {request.service.description}",
        f"CPT/HCPCS Codes: {', '.join(request.service.cpt_codes)}",
        f"Diagnosis Codes: {', '.join(request.service.icd10_codes)}",
        *_policy_lines(determination),
        "",
        f"Determination: {status_label}",
        "",
    ]

    if letter_type == "approval":
        valid_from = request.auth_valid_from or now.date().isoformat()
        valid_through = request.auth_valid_through or (
            now + timedelta(days=90)
        ).date().isoformat()
        lines += [
            f"Dear {request.provider.name},",
            "",
            "We are pleased to inform you that the prior authorization request referenced above "
            "has been APPROVED. The submitted clinical documentation supports medical necessity "
            "under the coverage policy cited above.",
            "",
            f"Authorization Number: {request.id}",
            f"Criteria Summary: {determination.criteria_met}",
            f"Valid From: {valid_from}",
            f"Valid Through: {valid_through}",
            "",
            f"Clinical Rationale: {determination.rationale}",
        ]
    else:
        response_deadline = (now + timedelta(days=_PEND_RESPONSE_DAYS)).strftime("%m/%d/%Y")
        lines += [
            f"Dear {request.provider.name},",
            "",
            "The prior authorization request referenced above cannot be completed at this time. "
            "This is not an adverse determination. The request has been placed in a pended status "
            "while we await additional clinical documentation.",
            "",
            f"Criteria Summary: {determination.criteria_met}",
            "",
            "Please submit the following documentation:",
        ]
        requested = request.requested_items or determination.gaps
        for index, item in enumerate(requested, start=1):
            lines.append(f"  {index}. {item}")
        lines += [
            "",
            f"Response Deadline: {response_deadline}",
            "",
            f"Clinical Rationale: {determination.rationale}",
            "",
            "Upon receipt of the requested documentation, this request will be re-reviewed "
            "promptly. You may also contact utilization management with any questions.",
        ]

    attribution = determination.attribution
    lines += [
        "",
        "Sincerely,",
        "Utilization Management Department",
        "",
        "----------------------------------------",
        "Determination Attribution:",
        f"  Engine: {attribution.engine_label}",
        f"  Model: {attribution.model_id or 'n/a'}",
        *[f"  {line.replace('Coverage Policy: ', 'Policy: ')}" for line in _policy_lines(determination)],
        f"  Evaluated At: {attribution.evaluated_at}",
    ]

    return Letter(
        request_id=request.id,
        letter_type=letter_type,
        subject=subject,
        body="\n".join(lines),
        generated_at=now.isoformat(),
    )
