"""Step 66A.0 -- Environment reset / staging cleanup / test handoff (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
TEST = ROOT / "docs" / "test"

REPORT = TEST / "environment-reset-and-test-handoff-report.md"
CLEANUP = STAGING / "staging-cleanup-record.md"
DEPLOY = TEST / "test-environment-reset-deployment-report.md"
SAFETY = TEST / "test-runtime-safety-validation.md"

DOCS = (REPORT, CLEANUP, DEPLOY, SAFETY)

FORBIDDEN = (
    "docker system prune -a",
    "docker volume prune",
    "rm -rf /data",
    "rm -rf /home/itadmin",
)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_staging_cleanup_scoped() -> None:
    low = _all_low()
    assert "aiagents-staging" in low
    assert "scoped to the aiagents-staging project" in low
    assert "down --volumes" in low


def test_secrets_not_printed_or_committed() -> None:
    low = _all_low()
    assert "staging secrets were not printed" in low
    assert "not committed" in low


def test_test_runtime_deployed() -> None:
    low = _all_low()
    assert "test runtime deployment completed" in low or "blocker" in low


def test_safety_invariants() -> None:
    low = _all_low()
    assert "production_executed_true_count=0" in low
    assert "no production action" in low
    assert "no unscoped docker prune" in low


def test_no_nonzero_prod_exec() -> None:
    low = _all_low()
    assert not re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low)


def test_no_forbidden_unscoped_commands_claimed() -> None:
    low = _all_low()
    for cmd in FORBIDDEN:
        # forbidden commands may only appear inside an explicit "no <cmd>" / "prune" negation context;
        # assert none of them appear as a claimed-executed instruction line.
        for line in low.splitlines():
            if cmd in line:
                assert ("no " in line) or ("never" in line) or ("not " in line), line


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for p in DOCS:
        assert not shapes.search(p.read_text(encoding="utf-8")), p.name
