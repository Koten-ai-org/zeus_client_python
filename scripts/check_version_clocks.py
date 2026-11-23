#!/usr/bin/env python3
"""Fail when the package version clocks disagree.

Clocks:
- pyproject.toml ``version``
- src/zeus_client/_version.py ``__version__``
- CHANGELOG.md heading ``## X.Y.Z``
- sdk_bootstrap.pins.json ``zeus_1_0_client.available_tag`` (``vX.Y.Z``)

Pass ``--tag vX.Y.Z`` on a release to require the tag to name that version.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

_VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.M)


def clock_errors(root: Path, tag: str | None = None) -> list[str]:
    """Return one message per clock that does not match the pyproject version."""
    errors: list[str] = []
    version = _pyproject_version(root, errors)
    if version is None:
        if tag is not None:
            errors.extend(_tag_errors(tag, None))
        return errors

    impl = _import_version(root, errors)
    if impl is not None and impl != version:
        errors.append(f"_version.py __version__ is {impl}; pyproject.toml version is {version}")

    if not _changelog_has_version(root, version, errors) and not any(
        msg.startswith("CHANGELOG.md") for msg in errors
    ):
        errors.append(f"CHANGELOG.md has no '## {version}' section")

    pins_tag = _pins_tag(root, errors)
    expect_tag = f"v{version}"
    if pins_tag is not None and pins_tag != expect_tag:
        errors.append(f"sdk_bootstrap.pins.json available_tag is {pins_tag}; expected {expect_tag}")

    if tag is not None:
        errors.extend(_tag_errors(tag, version))
    return errors


def _pyproject_version(root: Path, errors: list[str]) -> str | None:
    path = root / "pyproject.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"pyproject.toml: {exc}")
        return None
    except tomllib.TOMLDecodeError as exc:
        errors.append(f"pyproject.toml: {exc}")
        return None
    project = data.get("project")
    version = project.get("version") if isinstance(project, dict) else None
    if not isinstance(version, str) or not version:
        errors.append("pyproject.toml project.version is missing")
        return None
    return version


def _import_version(root: Path, errors: list[str]) -> str | None:
    path = root / "src" / "zeus_client" / "_version.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"_version.py: {exc}")
        return None
    match = _VERSION_RE.search(text)
    if match is None:
        errors.append("_version.py has no __version__ assignment")
        return None
    return match.group(1)


def _changelog_has_version(root: Path, version: str, errors: list[str]) -> bool:
    path = root / "CHANGELOG.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"CHANGELOG.md: {exc}")
        return False
    pattern = re.compile(rf"^## {re.escape(version)}(?:\s|$)", re.M)
    return pattern.search(text) is not None


def _pins_tag(root: Path, errors: list[str]) -> str | None:
    path = root / "sdk_bootstrap.pins.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"sdk_bootstrap.pins.json: {exc}")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"sdk_bootstrap.pins.json: {exc}")
        return None
    row = data.get("zeus_1_0_client")
    if not isinstance(row, dict):
        errors.append("sdk_bootstrap.pins.json has no zeus_1_0_client object")
        return None
    tag = row.get("available_tag")
    if not isinstance(tag, str) or not tag:
        errors.append("sdk_bootstrap.pins.json available_tag is missing")
        return None
    return tag


def _tag_errors(tag: str, version: str | None) -> list[str]:
    if not tag.startswith("v") or tag == "v":
        return [f"tag must look like vX.Y.Z, got {tag!r}"]
    if version is not None and tag[1:] != version:
        return [f"tag {tag} does not match pyproject.toml version {version}"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--tag", help="release tag, for example v2.5.4")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    errors = clock_errors(root, args.tag)
    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        return 1
    version = _pyproject_version(root, [])
    print(f"version clocks match {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
