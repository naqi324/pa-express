"""Local Medicare coverage files: data/cms-coverage/ncd-*.json and lcd-*.json.

This module never makes a network call. It scans the top level of the
coverage directory on each lookup, so a new ``lcd-*.json`` or ``ncd-*.json``
file becomes available without a code change or a restart.

File shapes:
- NCD files carry ``ncd_id`` (for example "150.3") and ``document_version``.
- LCD files carry the same fields as NCD files, plus ``lcd_id`` (for example
  "L12345") and ``contractor``. An LCD file may omit ``ncd_id``.

Files that cannot be read or parsed are skipped. The raw/ subdirectory
(API responses and eCFR extracts) is not scanned.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import AppError
from ..schemas import CoverageCheck, PolicySourceType

COVERAGE_DIR = Path(__file__).resolve().parents[3] / "data" / "cms-coverage"

_PREFIX = re.compile(r"^(ncd|lcd)[\s_:\-]*", re.IGNORECASE)
_NCD_ID = re.compile(r"^\d+(?:[.\-]\d+)*$")
_LCD_ID = re.compile(r"^l?[\s\-]*(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class PolicyKey:
    source_type: PolicySourceType
    # Canonical id: "150.3" for an NCD, "L12345" for an LCD.
    policy_id: str

    @property
    def code(self) -> str:
        return f"{self.source_type.upper()} {self.policy_id}"


@dataclass(frozen=True)
class PolicyFile:
    key: PolicyKey
    path: Path
    raw: dict[str, Any]


def normalize_policy_id(value: str) -> PolicyKey | None:
    """Map a user- or scenario-supplied policy id to its canonical key.

    Accepted NCD forms: "150.3", "150-3", "NCD 150.3", "ncd-150-3".
    Accepted LCD forms: "L12345", "l12345", "LCD L12345", "lcd-l12345", "LCD 12345".
    """
    text = value.strip()
    prefix_match = _PREFIX.match(text)
    prefix = prefix_match.group(1).lower() if prefix_match else None
    body = text[prefix_match.end():] if prefix_match else text
    body = body.strip()
    if not body:
        return None

    if prefix != "ncd":
        lcd_match = _LCD_ID.match(body)
        if lcd_match and (prefix == "lcd" or body[:1] in {"l", "L"}):
            return PolicyKey("lcd", f"L{lcd_match.group(1)}")
    if prefix != "lcd" and _NCD_ID.match(body):
        return PolicyKey("ncd", body.replace("-", "."))
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def contractor_name(raw: dict[str, Any]) -> str | None:
    """Read the contractor as a display string. Accepts a string, a dict, or a list."""
    value = raw.get("contractor")
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("contractor_name"))
    if isinstance(value, list):
        names = [contractor_name({"contractor": item}) for item in value]
        return "; ".join(name for name in names if name) or None
    return _text(value)


def document_version(raw: dict[str, Any]) -> str | None:
    for field in ("document_version", "version", "lcd_version", "ncd_version"):
        version = _text(raw.get(field))
        if version:
            return version
    return None


def _key_for_file(path: Path, raw: dict[str, Any]) -> PolicyKey | None:
    """Prefer the id declared inside the file; fall back to the file name."""
    source_type = "lcd" if path.name.lower().startswith("lcd-") else "ncd"
    declared = raw.get("lcd_id") if source_type == "lcd" else raw.get("ncd_id")
    candidates = [f"{source_type} {declared}"] if declared else []
    candidates.append(path.stem)
    for candidate in candidates:
        key = normalize_policy_id(candidate)
        if key is not None and key.source_type == source_type:
            return key
    return None


def iter_policy_files() -> list[PolicyFile]:
    """Every readable NCD and LCD file at the top level of the coverage directory."""
    if not COVERAGE_DIR.is_dir():
        return []
    files: list[PolicyFile] = []
    for path in sorted(COVERAGE_DIR.glob("*.json")):
        if not path.is_file() or not path.name.lower().startswith(("ncd-", "lcd-")):
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        key = _key_for_file(path, raw)
        if key is not None:
            files.append(PolicyFile(key=key, path=path, raw=raw))
    return files


def find_policy_file(policy_id: str) -> PolicyFile | None:
    key = normalize_policy_id(policy_id)
    if key is None:
        return None
    return next((item for item in iter_policy_files() if item.key == key), None)


def coverage_check_from_file(policy_file: PolicyFile) -> CoverageCheck:
    raw = policy_file.raw
    key = policy_file.key
    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    version = document_version(raw)
    summary = raw.get("covered_indication_summary") or raw.get("coverage_model") or ""
    return CoverageCheck(
        policy_id=key.policy_id,
        source_type=key.source_type,
        version=version,
        title=str(raw.get("title", "")),
        covered=True,
        summary=str(summary),
        source_url=str(source.get("mcd_url") or source.get("api_url") or ""),
        ncd_id=key.policy_id if key.source_type == "ncd" else None,
        ncd_version=version if key.source_type == "ncd" else None,
        lcd_id=key.policy_id if key.source_type == "lcd" else None,
        contractor=contractor_name(raw) if key.source_type == "lcd" else None,
    )


def load_coverage_check(policy_id: str) -> CoverageCheck:
    policy_file = find_policy_file(policy_id)
    if policy_file is None:
        raise AppError(
            404,
            "COVERAGE_NOT_FOUND",
            f"No local coverage document is available for policy '{policy_id}'.",
            "Use an NCD id such as 150.3 or an LCD id such as L12345, or add the "
            "coverage JSON to data/cms-coverage/.",
        )
    return coverage_check_from_file(policy_file)
