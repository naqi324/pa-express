#!/usr/bin/env python3
"""Verify that VERSION, pyproject.toml, and package.json carry the same version."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def main() -> int:
    version_path = ROOT_DIR / "VERSION"
    package_path = ROOT_DIR / "package.json"
    pyproject_path = ROOT_DIR / "pyproject.toml"

    canonical_version = read_text(version_path)
    package_version = json.loads(read_text(package_path))["version"]
    pyproject_version = tomllib.loads(read_text(pyproject_path))["project"]["version"]

    errors: list[str] = []
    if not SEMVER_RE.fullmatch(canonical_version):
        errors.append(f"VERSION must use MAJOR.MINOR.PATCH, found {canonical_version!r}.")
    if package_version != canonical_version:
        errors.append(f"package.json version {package_version!r} does not match VERSION {canonical_version!r}.")
    if pyproject_version != canonical_version:
        errors.append(f"pyproject.toml version {pyproject_version!r} does not match VERSION {canonical_version!r}.")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Version metadata is in sync: {canonical_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
