"""Step 64F.3 -- Controlled orchestrator rebuild/redeploy rehearsal (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "deployment-management-rebuild-redeploy-rehearsal-report.md"
EVIDENCE = STAGING / "deployment-management-rebuild-redeploy-before-after-evidence.md"
VALIDATION = STAGING / "deployment-management-rebuild-redeploy-validation-result.md"
GAPS = STAGING / "deployment-management-rebuild-redeploy-known-gaps.md"
SAFETY = STAGING / "deployment-management-rebuild-redeploy-safety-record.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, EVIDENCE, VALIDATION, GAPS, SAFETY)
NOT_EXECUTED = (
    "no full-stack rebuild",
    "no full-stack restart",
    "no teardown",
    "no restore",
    "no rollback",
    "no workflow re-run",
    "no image push",
    "no production action",
)


def test_rehearsal_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_orchestrator_only_rebuild_redeploy_scope_documented() -> None:
    report_low = REPORT.read_text(encoding="utf-8").lower()
    assert "build orchestrator" in report_low
    assert "up -d orchestrator" in report_low
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "ff-only" in low or "fast-forward" in low


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
    assert "rebuild_redeploy_rehearsal_completed" in low


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


def test_step64f3_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64F.3" in text
    assert "CONTROLLED_ORCHESTRATOR_REBUILD_REDEPLOY_REHEARSAL_VERIFY" in text
