"""Step 64F.2 -- Controlled staging operations rehearsal (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "deployment-management-rehearsal-report.md"
EVIDENCE = STAGING / "deployment-management-rehearsal-before-after-evidence.md"
CHECKLIST = STAGING / "deployment-management-rehearsal-operator-checklist-result.md"
GAPS = STAGING / "deployment-management-rehearsal-known-gaps.md"
SAFETY = STAGING / "deployment-management-rehearsal-safety-record.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, EVIDENCE, CHECKLIST, GAPS, SAFETY)
NOT_EXECUTED = (
    "no rebuild",
    "no full-stack restart",
    "no teardown",
    "no restore",
    "no workflow re-run",
    "no production action",
)


def test_rehearsal_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_orchestrator_only_scope_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "orchestrator-only restart" in low
    assert "restart orchestrator" in REPORT.read_text(encoding="utf-8").lower()


def test_forbidden_commands_documented_not_executed() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    for phrase in NOT_EXECUTED:
        assert phrase in low, phrase
    assert "down -v" in low and "no down and no down -v occurred" in low


def test_validation_and_no_data_loss() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "/health" in low and "/operations/safety" in low
    assert "no data loss" in low


def test_status_recorded() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64e" in low and "pass" in low
    assert "rehearsal_completed" in low


def test_prod_exec_zero_and_no_production_action() -> None:
    combined = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert any(
        t in combined for t in ("production_executed_true_count=0", "prod_exec=0", "remained 0")
    )
    for p in DOCS:
        assert "no production action" in p.read_text(encoding="utf-8").lower(), p.name


def test_safety_flags_present() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step64f2_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64F.2" in text
    assert "CONTROLLED_STAGING_OPERATIONS_REHEARSAL_VERIFY" in text
