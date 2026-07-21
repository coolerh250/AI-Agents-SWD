"""Step 66ALIGN.2-R1 -- project completion master plan ownership remediation (docs-only checks).

This file changes no runtime code. It confirms the ownership remediation record and remediation
test record exist and state: Step 66C.4 primary implementation owner is Claude Code (scheduler/
expiry/resume/backend/workflow), Codex is limited to explicitly authorized frontend slices, M3
owns product-level Team RBAC implementation, M6/M7 own production identity/session/provisioning
hardening without deferring M3's implementation, FE.1D-S2 is not an unresolved PO decision (remains
unauthorized/non-critical), the canonical milestone order is unchanged, Step 66C.4-P remains not
started, no runtime/backend/API/database/workflow change or deployment is claimed, alignment
branches remain unmerged, and source/progress.md is updated.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "docs" / "alignment" / "66-project-completion" / "master"

OWNERSHIP_RECORD = MASTER_DIR / "ownership-remediation-record.md"
REMEDIATION_TEST_RECORD = (
    ROOT / "docs" / "test" / "step66align2-project-completion-master-plan-remediation-record.md"
)

MASTER_DOCS = {
    "master-plan": MASTER_DIR / "project-completion-master-plan.md",
    "canonical-milestone-manifest": MASTER_DIR / "canonical-milestone-manifest.md",
    "critical-path-and-dependency-map": MASTER_DIR / "critical-path-and-dependency-map.md",
    "role-ownership-matrix": MASTER_DIR / "role-ownership-matrix.md",
    "product-and-technical-gates": MASTER_DIR / "product-and-technical-gates.md",
    "project-definition-of-done": MASTER_DIR / "project-definition-of-done.md",
    "next-executable-stage-sequence": MASTER_DIR / "next-executable-stage-sequence.md",
    "cross-partner-resolution-record": MASTER_DIR / "cross-partner-resolution-record.md",
    "product-owner-review-checklist": MASTER_DIR / "product-owner-review-checklist.md",
    "ownership-remediation-record": OWNERSHIP_RECORD,
}

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-remediation"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-remediation"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-remediation"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

ALIGNMENT_BRANCH_NAMES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

ALL_TEXT_DOCS = {**MASTER_DOCS, "remediation-test-record": REMEDIATION_TEST_RECORD}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in ALL_TEXT_DOCS.values())


def test_ownership_record_exists() -> None:
    assert OWNERSHIP_RECORD.is_file()


def test_remediation_test_record_exists() -> None:
    assert REMEDIATION_TEST_RECORD.is_file()


def test_stage_docs_exist() -> None:
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66align.2-r1" in text


def test_claude_code_primary_step_66c4_owner() -> None:
    text = _norm(_all_text())
    assert re.search(r"claude code[^.]{0,80}primary[^.]{0,40}(owner|implementation)", text)
    for term in ("scheduler", "expiry", "resume", "backend", "workflow"):
        assert term in text, term


def test_codex_limited_to_authorized_frontend_slice() -> None:
    text = _norm(_all_text())
    assert "explicitly authorized frontend" in text or "explicitly authorized" in text


def test_m3_owns_team_rbac_implementation() -> None:
    text = _norm(_all_text())
    assert "m3 owns" in text or "m3 implements" in text


def test_m6_m7_own_production_identity_hardening() -> None:
    text = _norm(_all_text())
    assert "m6/m7" in text
    assert "identity" in text
    assert "session" in text
    assert "provisioning" in text


def test_m6_does_not_defer_m3_rbac_implementation() -> None:
    text = _norm(_all_text())
    assert re.search(
        r"not deferred to m6|not defer(?:red|ring)? m3|implemented and validated in m3", text
    )


def test_fe1d_s2_not_unresolved_po_decision() -> None:
    text = _norm(_all_text())
    assert "not listed as an unresolved" in text or "not framed as an open decision" in text


def test_fe1d_s2_unauthorized_non_critical() -> None:
    text = _norm(_all_text())
    assert re.search(r"fe\.1d-s2[^.]{0,60}(unauthorized|non-critical)", text)


def test_canonical_milestone_order_unchanged() -> None:
    order_doc = MASTER_DOCS["master-plan"].read_text(encoding="utf-8").lower()
    assert "m0 -> m1 -> m2 -> m3 -> m4 -> m5 -> m6 -> m7" in order_doc


def test_step_66c4p_remains_not_started() -> None:
    text = _norm(_all_text())
    assert "66c.4-p" in text
    assert "not started" in text


def test_no_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term


def test_no_deployment_claimed() -> None:
    text = _norm(_all_text())
    assert "no deployment" in text


def test_alignment_branches_remain_unmerged() -> None:
    text = _norm(_all_text())
    for branch in ALIGNMENT_BRANCH_NAMES:
        assert branch in text, branch
    assert "unmerged" in text


def test_marker_pass_present() -> None:
    text = REMEDIATION_TEST_RECORD.read_text(encoding="utf-8")
    assert "STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_REMEDIATION_VERIFY: PASS" in text
