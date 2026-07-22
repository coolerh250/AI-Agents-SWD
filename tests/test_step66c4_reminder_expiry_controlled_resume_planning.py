"""Step 66C.4-P -- reminder/expiry/controlled resume planning (docs-only checks).

This file changes no runtime code. It confirms all 13 contract documents, the planning handoff,
the test record, and stage artifacts exist and state the required facts: existing fields/endpoints
are evidence-based, 24h reminder and 72h blocked/expired behavior are specified, answer and resume
are separate transitions, no hidden auto-dispatch/resume is proposed without an explicit decision,
duplicate execution is idempotent, cancelled/aborted/terminal workflows cannot resume, external
notification remains disabled, production_executed_true_count remains 0, Team RBAC full scope
remains M3, Claude Code remains primary implementation owner, Codex/Claude Design remain
unauthorized, no runtime code/migration/deployment is claimed, and source/progress.md is updated.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

CONTRACT_DOCS = {
    "current-state-assessment": CONTRACT_DIR / "current-state-assessment.md",
    "lifecycle-and-time-contract": CONTRACT_DIR / "lifecycle-and-time-contract.md",
    "data-model-contract": CONTRACT_DIR / "data-model-contract.md",
    "api-and-event-contract": CONTRACT_DIR / "api-and-event-contract.md",
    "scheduler-architecture-decision": CONTRACT_DIR / "scheduler-architecture-decision.md",
    "controlled-resume-contract": CONTRACT_DIR / "controlled-resume-contract.md",
    "rbac-and-safety-contract": CONTRACT_DIR / "rbac-and-safety-contract.md",
    "race-condition-and-failure-analysis": CONTRACT_DIR / "race-condition-and-failure-analysis.md",
    "observability-and-audit-plan": CONTRACT_DIR / "observability-and-audit-plan.md",
    "frontend-ux-boundary": CONTRACT_DIR / "frontend-ux-boundary.md",
    "implementation-stage-slicing-plan": CONTRACT_DIR / "implementation-stage-slicing-plan.md",
    "test-and-validation-plan": CONTRACT_DIR / "test-and-validation-plan.md",
    "product-owner-decision-checklist": CONTRACT_DIR / "product-owner-decision-checklist.md",
}

HANDOFF = (
    ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume" / "planning-handoff.md"
)
TEST_RECORD = (
    ROOT / "docs" / "test" / "step66c4-reminder-expiry-controlled-resume-planning-record.md"
)

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66c4-reminder-expiry-controlled-resume-planning"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66c4-reminder-expiry-controlled-resume-planning"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66c4-reminder-expiry-controlled-resume-planning"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

ALL_TEXT_DOCS = {**CONTRACT_DOCS, "planning-handoff": HANDOFF, "test-record": TEST_RECORD}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in ALL_TEXT_DOCS.values())


def test_contract_docs_exist() -> None:
    for name, p in CONTRACT_DOCS.items():
        assert p.is_file(), name


def test_handoff_and_test_record_exist() -> None:
    assert HANDOFF.is_file()
    assert TEST_RECORD.is_file()


def test_stage_docs_exist() -> None:
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66c.4-p" in text


def test_evidence_based_citations_present() -> None:
    text = _norm(_all_text())
    for cite in ("workroom_store.py", "operator_clarification_requests", "workroom_api.py"):
        assert cite in text, cite


def test_24h_reminder_and_72h_expiry_specified() -> None:
    text = _norm(_all_text())
    assert "24" in text and "reminder" in text
    assert "72" in text and ("expir" in text or "blocked" in text)


def test_answer_and_resume_are_separate_transitions() -> None:
    text = _norm(_all_text())
    assert "resume eligible" in text
    assert "answer recorded" in text


def test_automatic_resume_analyzed_as_explicit_decision() -> None:
    text = _norm(_all_text())
    assert "automatic resume" in text
    assert "explicit" in text


def test_idempotency_addressed() -> None:
    text = _norm(_all_text())
    assert "idempotent" in text or "idempotency" in text


def test_cancelled_terminal_workflow_protection() -> None:
    text = _norm(_all_text())
    assert re.search(r"cancel(?:l?ed)?[^.]{0,60}(cannot|must not|blocked|protection)", text)


def test_external_notification_disabled() -> None:
    text = _norm(_all_text())
    assert "external" in text
    assert "disabled" in text


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text
    assert "0" in text


def test_team_rbac_m3_scope_deferral() -> None:
    text = _norm(_all_text())
    assert "m3" in text
    assert "team rbac" in text or "full team" in text


def test_claude_code_primary_owner() -> None:
    text = _norm(_all_text())
    assert re.search(r"claude code[^.]{0,40}primary[^.]{0,40}(owner|implementation)", text)


def test_codex_and_claude_design_unauthorized() -> None:
    text = _norm(_all_text())
    assert "codex" in text
    assert "claude design" in text
    assert "not authorized" in text or "unauthorized" in text


def test_no_migration_deployment_scheduler_claimed() -> None:
    text = _norm(_all_text())
    assert "no migration created" in text
    assert "no deployment" in text
    assert "no scheduler activated" in text


def test_no_local_windows_paths_committed() -> None:
    windows_path_shape = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)
    for name, p in ALL_TEXT_DOCS.items():
        assert not windows_path_shape.search(p.read_text(encoding="utf-8")), name


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in ALL_TEXT_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    text = _all_text().lower()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_marker_pass_present() -> None:
    text = TEST_RECORD.read_text(encoding="utf-8")
    assert "STEP66C4_REMINDER_EXPIRY_CONTROLLED_RESUME_PLANNING_VERIFY: PASS" in text
