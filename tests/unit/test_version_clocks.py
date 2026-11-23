"""Version clocks stay in lockstep: pyproject, _version, changelog, pins."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_version_clocks.py"


def _write_repo(
    root: Path,
    version: str = "1.2.3",
    *,
    changelog: str | None = None,
    pins_tag: str | None = None,
    import_version: str | None = None,
) -> None:
    (root / "src" / "zeus_client").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "kotenai-zeus-client"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    impl = version if import_version is None else import_version
    (root / "src" / "zeus_client" / "_version.py").write_text(
        f'__version__ = "{impl}"\n',
        encoding="utf-8",
    )
    notes = f"## {version} — 2026-01-01\n" if changelog is None else changelog
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n{notes}\n", encoding="utf-8")
    tag = f"v{version}" if pins_tag is None else pins_tag
    (root / "sdk_bootstrap.pins.json").write_text(
        json.dumps({"zeus_1_0_client": {"available_tag": tag}}),
        encoding="utf-8",
    )


def _run(*args: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_matching_clocks_pass(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    result = _run(root=tmp_path)
    assert result.returncode == 0
    assert "1.2.3" in result.stdout


def test_tag_must_match_version(tmp_path: Path) -> None:
    _write_repo(tmp_path)
    ok = _run("--tag", "v1.2.3", root=tmp_path)
    bad = _run("--tag", "v9.9.9", root=tmp_path)
    assert ok.returncode == 0
    assert bad.returncode == 1
    assert "v9.9.9" in bad.stderr


def test_changelog_prefix_is_not_a_match(tmp_path: Path) -> None:
    _write_repo(tmp_path, changelog="## 1.2.30 — 2026-01-01\n")
    result = _run(root=tmp_path)
    assert result.returncode == 1
    assert "CHANGELOG.md" in result.stderr


def test_each_clock_mismatch_fails(tmp_path: Path) -> None:
    _write_repo(tmp_path, import_version="9.9.9", changelog="## Unreleased\n", pins_tag="v0.0.1")
    result = _run(root=tmp_path)
    assert result.returncode == 1
    assert "__version__" in result.stderr
    assert "CHANGELOG.md" in result.stderr
    assert "available_tag" in result.stderr


def test_repo_clocks_match() -> None:
    result = _run(root=ROOT)
    assert result.returncode == 0, result.stderr
    assert "2.5.4" in result.stdout
