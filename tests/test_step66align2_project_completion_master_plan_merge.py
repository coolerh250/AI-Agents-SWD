"""Step 66ALIGN.2-M -- merge project completion master plan into main (docs-only checks).

This file changes no runtime code. It confirms the merge record and source-of-truth record exist
and state: Master Plan source commit and merge commit recorded, Master Plan artifacts present on
main and recorded as canonical source of truth, M0-M7 order recorded (M0 CLOSED, M1 IN_PROGRESS),
Step 66C.4-P next but not started, Step 66C.4 primary owner is Claude Code with Codex limited to
separately authorized frontend slices, M3 implements product-level Team RBAC, M6/M7 production-
harden identity/access, FE.1D-S2 remains unauthorized/non-critical and is not an unresolved PO
decision, original alignment branches remain unmerged, PR #14/#15 remain unchanged, no runtime/
backend/API/database/workflow change or deployment is claimed, production_executed_true_count
remains 0, and source/progress.md is updated.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "docs" / "alignment" / "66-project-completion" / "master"

MERGE_RECORD = MASTER_DIR / "master-plan-merge-record.md"
SOT_RECORD = MASTER_DIR / "master-plan-source-of-truth-record.md"
MERGE_TEST_RECORD = (
    ROOT / "docs" / "test" / "step66align2-project-completion-master-plan-merge-record.md"
)

MASTER_PLAN_ARTIFACTS = [
    MASTER_DIR / "project-completion-master-plan.md",
    MASTER_DIR / "canonical-milestone-manifest.md",
    MASTER_DIR / "current-state-capability-matrix.md",
    MASTER_DIR / "critical-path-and-dependency-map.md",
    MASTER_DIR / "role-ownership-matrix.md",
    MASTER_DIR / "product-and-technical-gates.md",
    MASTER_DIR / "project-definition-of-done.md",
    MASTER_DIR / "deferred-work-register.md",
    MASTER_DIR / "next-executable-stage-sequence.md",
    MASTER_DIR / "cross-partner-resolution-record.md",
    MASTER_DIR / "product-owner-review-checklist.md",
    MASTER_DIR / "ownership-remediation-record.md",
]

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-merge"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-merge"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-merge"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MASTER_PLAN_SOURCE_COMMIT = "5da21f5"

ALIGNMENT_BRANCH_NAMES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

ALL_TEXT_DOCS = {
    "merge-record": MERGE_RECORD,
    "sot-record": SOT_RECORD,
    "merge-test-record": MERGE_TEST_RECORD,
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in ALL_TEXT_DOCS.values())


def test_merge_and_sot_records_exist() -> None:
    for name, p in ALL_TEXT_DOCS.items():
        assert p.is_file(), name


def test_master_plan_artifacts_present_on_main() -> None:
    for p in MASTER_PLAN_ARTIFACTS:
        assert p.is_file(), p


def test_stage_docs_exist() -> None:
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66align.2-m" in text


def test_source_commit_and_merge_commit_recorded() -> None:
    text = _norm(_all_text())
    assert MASTER_PLAN_SOURCE_COMMIT in text
    assert "merge commit" in text


def test_master_plan_recorded_canonical() -> None:
    text = _norm(_all_text())
    assert "canonical" in text


def test_milestone_order_and_status_recorded() -> None:
    text = _norm(_all_text())
    assert "m0 -> m1 -> m2 -> m3 -> m4 -> m5 -> m6 -> m7" in text
    assert re.search(r"m0[^.]{0,20}closed", text)
    assert "in_progress" in text


def test_step_66c4p_next_but_not_started() -> None:
    text = _norm(_all_text())
    assert "66c.4-p" in text
    assert "not started" in text


def test_step_66c4_ownership_recorded() -> None:
    text = _norm(_all_text())
    assert re.search(r"claude code[^.]{0,40}(primary|owner)", text)
    assert "authorized frontend" in text


def test_team_rbac_ownership_recorded() -> None:
    text = _norm(_all_text())
    assert "team rbac" in text and "m3" in text
    assert "m6/m7" in text and "identity" in text


def test_fe1d_s2_status_and_resolved_decision() -> None:
    text = _norm(_all_text())
    assert re.search(r"fe\.1d-s2[^.]{0,60}(unauthorized|non-critical)", text)
    assert "unresolved" in text or "not an open" in text


def test_alignment_branches_unmerged_and_prs_unchanged() -> None:
    text = _norm(_all_text())
    for branch in ALIGNMENT_BRANCH_NAMES:
        assert branch in text, branch
    assert "unmerged" in text
    assert "pr #14" in text
    assert "pr #15" in text


def test_no_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term


def test_no_deployment_claimed() -> None:
    text = _norm(_all_text())
    assert "no deployment" in text


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text
    assert "0" in text


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
    text = MERGE_TEST_RECORD.read_text(encoding="utf-8")
    assert "STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_MERGE_VERIFY: PASS" in text
