"""Step 54.3 -- Dockerfile security inventory."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "dockerfile-security-inventory.yaml"


def _dfs() -> list:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("dockerfiles", [])


def test_covers_all_repo_dockerfiles() -> None:
    actual = [
        f
        for f in subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
        ).stdout.split()
        if f.endswith("Dockerfile")
    ]
    assert len(_dfs()) == len(actual)


def test_root_gaps_recorded() -> None:
    dfs = _dfs()
    roots = [d for d in dfs if d["runsAsRootByDefault"]]
    assert roots  # all 20 run as root
    for d in dfs:
        assert isinstance(d["hasUserInstruction"], bool)


def test_non_root_not_falsely_claimed() -> None:
    for d in _dfs():
        if not d["hasUserInstruction"]:
            assert d["runsAsRootByDefault"] is True


def test_no_secret_copy() -> None:
    for d in _dfs():
        assert d["copiesSecrets"] is False
