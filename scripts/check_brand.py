#!/usr/bin/env python3
"""Fail when a retired vendor name, product, or identifier appears in the repo.

The search terms are base64-encoded so this guard does not itself carry the
names it keeps out. The scan covers tracked and untracked (non-ignored) files,
the built bundle in dist/ when present, and every commit message.
"""

from __future__ import annotations

import base64
import re
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

# (base64 regex, case-insensitive flag)
ENCODED_TERMS: tuple[tuple[str, bool], ...] = (
    ("XGJNQ0dcYg==", False),
    ("XGJtY2dbLV9d", True),
    ("XGJpW01tXVtDY11bR2ddXGI=", False),
    ("c3luYXBzZQ==", True),
    ("XGJtdWNsXGI=", True),
    ("QHV4ZVxi", True),
    ("Y2FyZXdlYnFp", True),
    ("aGVhcnN0", True),
    ("aW50ZXJxdWFs", True),
    ("aW5kaWNpYQ==", True),
    ("bWlsbGltYW4=", True),
    ("aW5kaWNhdGlvbnNldA==", True),
    ("XGJBLTAwNTJcYg==", False),
    ("XGJBLTAxNDVcYg==", False),
    ("XGJTLTcwMFxi", False),
    ("Zm9yZXZlci1jbGF1ZGU=", True),
    ("Y29nbml0bw==", True),
)

SKIP_PARTS = {"node_modules", ".git", ".venv", ".Codex", "__pycache__"}

# Lockfile integrity hashes are base64 and can spell anything.
SKIP_LINE = re.compile(r"^\s*(integrity:|resolution: \{integrity)")


def patterns() -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []

    for encoded, ignore_case in ENCODED_TERMS:
        source = base64.b64decode(encoded).decode("utf-8")
        compiled.append(re.compile(source, re.IGNORECASE if ignore_case else 0))

    return compiled


def candidate_files() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")

    files = [ROOT_DIR / name for name in listed.split("\0") if name]

    dist = ROOT_DIR / "dist"

    if dist.is_dir():
        files.extend(path for path in dist.rglob("*") if path.is_file())

    return [
        path
        for path in files
        if path.is_file() and path.resolve() != SELF and not SKIP_PARTS.intersection(path.relative_to(ROOT_DIR).parts)
    ]


def scan_text(label: str, text: str, compiled: list[re.Pattern[str]]) -> list[str]:
    hits: list[str] = []

    for number, line in enumerate(text.splitlines(), start=1):
        if SKIP_LINE.match(line):
            continue

        for pattern in compiled:
            match = pattern.search(line)

            if match:
                hits.append(f"{label}:{number}: retired term '{match.group(0)}'")

    return hits


def commit_messages() -> str:
    result = subprocess.run(
        ["git", "log", "--all", "--format=%H%n%B%n"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )

    return result.stdout if result.returncode == 0 else ""


def main() -> int:
    compiled = patterns()

    hits: list[str] = []

    scanned = 0

    for path in candidate_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        scanned += 1
        hits.extend(scan_text(str(path.relative_to(ROOT_DIR)), text, compiled))

    hits.extend(scan_text("git log", commit_messages(), compiled))

    if hits:
        print("Brand check failed:", file=sys.stderr)

        for hit in hits:
            print(f"  {hit}", file=sys.stderr)

        return 1

    print(f"Brand check passed ({scanned} files and all commit messages scanned).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
