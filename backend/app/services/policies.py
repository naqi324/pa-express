"""Policy labels, attribution fields, and the local-only policy document lookup.

A policy is a Medicare National Coverage Determination (NCD) or a Local
Coverage Determination (LCD). Every value here comes from a scenario's
``policy`` dict or from a local file in data/cms-coverage/. Nothing here makes
a network call.
"""

from typing import Any

from ..errors import AppError
from ..schemas import (
    Attribution,
    PolicyCriterion,
    PolicyDocument,
    PolicySection,
    ReviewCriteriaSet,
    ReviewCriterion,
)
from .coverage import (
    PolicyFile,
    PolicyKey,
    contractor_name,
    document_version,
    find_policy_file,
    normalize_policy_id,
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def policy_key(policy: dict) -> PolicyKey | None:
    """The canonical key of a scenario policy dict, if it names an NCD or LCD."""
    source_type = policy.get("source_type")
    if source_type == "lcd":
        raw_id = policy.get("lcd_id") or policy.get("code")
    elif source_type == "ncd":
        raw_id = policy.get("ncd_id") or policy.get("code")
    else:
        return None
    if not raw_id:
        return None
    key = normalize_policy_id(f"{source_type} {raw_id}")
    return key if key is not None and key.source_type == source_type else None


def policy_version(policy: dict) -> str | None:
    return _clean(policy.get("version")) or _clean(policy.get("ncd_version"))


def policy_label(policy: dict) -> str:
    """Short label used in rationale text, e.g. "NCD 150.3 (version 2)"."""
    key = policy_key(policy)
    version = policy_version(policy)
    suffix = f" (version {version})" if version else ""
    if key is not None:
        return f"{key.code}{suffix}"
    return (_clean(policy.get("code")) or _clean(policy.get("title")) or "the cited policy") + suffix


def scenario_policy_label(scenario: dict) -> str:
    """Worklist label, e.g. "Medicare NCD 150.3" or "Medicare LCD L12345"."""
    if scenario.get("policy_label"):
        return str(scenario["policy_label"])
    policy = scenario.get("policy") or {}
    key = policy_key(policy)
    if key is not None:
        return f"Medicare {key.code}"
    return _clean(policy.get("code")) or ""


def attribution_policy_fields(policy: dict) -> dict[str, Any]:
    """Policy fields for an Attribution, derived from a scenario policy dict."""
    source_type = policy.get("source_type")
    return {
        "policy_source_type": source_type if source_type in {"ncd", "lcd"} else None,
        "policy_code": _clean(policy.get("code")),
        "policy_title": _clean(policy.get("title")),
        "policy_version": policy_version(policy),
        "ncd_id": _clean(policy.get("ncd_id")),
        "ncd_version": _clean(policy.get("ncd_version")),
        "lcd_id": _clean(policy.get("lcd_id")),
        "contractor": _clean(policy.get("contractor")),
    }


def letter_policy_line(attribution: Attribution) -> str:
    """The "Coverage Policy:" line of a provider letter.

    NCD: ``Coverage Policy: Medicare NCD 150.3 (Version 2)``
    LCD: ``Coverage Policy: Medicare LCD L12345 — <title> (<contractor>)``
    """
    if attribution.policy_source_type == "lcd" or attribution.lcd_id:
        lcd_id = attribution.lcd_id or attribution.policy_code or ""
        key = normalize_policy_id(f"lcd {lcd_id}") if lcd_id else None
        line = f"Coverage Policy: Medicare LCD {key.policy_id if key else lcd_id}".rstrip()
        if attribution.policy_title:
            line += f" — {attribution.policy_title}"
        if attribution.contractor:
            line += f" ({attribution.contractor})"
        return line
    if attribution.ncd_id:
        version = attribution.ncd_version or attribution.policy_version
        suffix = f" (Version {version})" if version else ""
        return f"Coverage Policy: Medicare NCD {attribution.ncd_id}{suffix}"
    label = attribution.policy_code or attribution.policy_title or "Not specified"
    return f"Coverage Policy: {label}"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    return [str(value)]


def _criteria_from_file(raw: dict[str, Any]) -> list[PolicyCriterion]:
    criteria: list[PolicyCriterion] = []
    for index, item in enumerate(raw.get("criteria") or [], start=1):
        if not isinstance(item, dict):
            continue
        text = _clean(item.get("text"))
        if not text:
            continue
        criteria.append(
            PolicyCriterion(
                id=_clean(item.get("id")) or f"C{index}",
                text=text,
                category=_clean(item.get("category")),
                required=bool(item.get("required", True)),
                logic=_clean(item.get("logic")),
                options=_string_list(item.get("options")),
                check_hints=_string_list(item.get("check_hints")),
            )
        )
    return criteria


def _section_title(key: str) -> str:
    words = key.replace("_", " ").split()
    acronyms = {"cms", "ncd", "lcd", "ecfr", "cfr"}
    return " ".join(word.upper() if word in acronyms else word.capitalize() for word in words)


def _paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [" ".join(block.split()) for block in normalized.split("\n\n")]
    return [block for block in blocks if block]


def _sections_from_file(raw: dict[str, Any]) -> list[PolicySection]:
    full_text = raw.get("full_text")
    if not isinstance(full_text, dict):
        return []
    sections: list[PolicySection] = []
    for key, value in full_text.items():
        if isinstance(value, list):
            paragraphs = [p for item in value for p in _paragraphs(str(item))]
        elif value is None:
            paragraphs = []
        else:
            paragraphs = _paragraphs(str(value))
        if paragraphs:
            sections.append(PolicySection(key=str(key), title=_section_title(str(key)), paragraphs=paragraphs))
    return sections


def _review_criteria(key: PolicyKey, scenarios: list[dict]) -> list[ReviewCriteriaSet]:
    sets: list[ReviewCriteriaSet] = []
    for scenario in scenarios:
        if policy_key(scenario.get("policy") or {}) != key:
            continue
        sets.append(
            ReviewCriteriaSet(
                scenario_id=str(scenario.get("id", "")),
                scenario_title=str(scenario.get("title", scenario.get("id", ""))),
                criteria=[
                    ReviewCriterion(
                        criterion_id=str(item.get("criterion_id", "")),
                        criterion_text=str(item.get("criterion_text", "")),
                        depth=int(item.get("depth", 0)),
                        logic=item.get("logic"),
                    )
                    for item in scenario.get("criteria") or []
                ],
            )
        )
    return sets


def _document_from_file(policy_file: PolicyFile) -> PolicyDocument:
    raw = policy_file.raw
    key = policy_file.key
    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    return PolicyDocument(
        policy_id=key.policy_id,
        source_type=key.source_type,
        code=key.code,
        title=str(raw.get("title", "")),
        version=document_version(raw),
        contractor=contractor_name(raw) if key.source_type == "lcd" else None,
        # NCD files carry effective_date; LCD files carry revision/original dates.
        effective_date=_clean(raw.get("effective_date"))
        or _clean(raw.get("revision_effective_date"))
        or _clean(raw.get("original_effective_date")),
        last_updated=_clean(raw.get("last_updated")),
        benefit_category=_clean(raw.get("benefit_category")),
        coverage_model=_clean(raw.get("coverage_model")),
        summary=str(raw.get("covered_indication_summary") or raw.get("coverage_model") or ""),
        source_url=_clean(source.get("mcd_url")) or _clean(source.get("api_url")),
        api_url=_clean(source.get("api_url")),
        local_file_available=True,
        criteria=_criteria_from_file(raw),
        non_covered=_string_list(raw.get("non_covered")),
        notes=_string_list(raw.get("notes")),
        sections=_sections_from_file(raw),
    )


def _document_from_scenario(key: PolicyKey, policy: dict) -> PolicyDocument:
    return PolicyDocument(
        policy_id=key.policy_id,
        source_type=key.source_type,
        code=key.code,
        title=str(policy.get("title", "")),
        version=policy_version(policy),
        contractor=_clean(policy.get("contractor")),
        source_url=_clean(policy.get("source_url")),
        local_file_available=False,
    )


def load_policy_document(policy_id: str, scenarios: list[dict]) -> PolicyDocument:
    """Build a PolicyDocument from local files and the scenarios' authored criteria.

    Raises 404 POLICY_NOT_FOUND when the id is not an NCD or LCD id, or when
    neither a local file nor a scenario cites the policy.
    """
    key = normalize_policy_id(policy_id)
    if key is not None:
        review_criteria = _review_criteria(key, scenarios)
        policy_file = find_policy_file(policy_id)
        if policy_file is not None:
            document = _document_from_file(policy_file)
            document.review_criteria = review_criteria
            return document
        citing = next(
            (s for s in scenarios if policy_key(s.get("policy") or {}) == key),
            None,
        )
        if citing is not None:
            document = _document_from_scenario(key, citing.get("policy") or {})
            document.review_criteria = review_criteria
            return document
    raise AppError(
        404,
        "POLICY_NOT_FOUND",
        f"No local policy document is available for '{policy_id}'.",
        "Use an NCD id such as 150.3 or an LCD id such as L12345 that has a file in "
        "data/cms-coverage/ or is cited by a scenario.",
    )
