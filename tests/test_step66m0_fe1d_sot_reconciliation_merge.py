"""Step 66M0-SOT-RECONCILE-M -- merge and close FE.1D source-of-truth gap (docs-only checks).

This file changes no runtime code. It confirms the source-of-truth closure record, merge execution
record, Team RBAC decision record, test record, and stage artifacts exist and state the required
facts: all three FE.1D branches merged with source/merge commits recorded, FE.1D-S1 COMPLETE/
SHIPPED, FE.1D-S2 UNAUTHORIZED/NON-CRITICAL, "+ Create task" unchanged, delivery_package_ready_for_
admin_console rename deferred to 66D, workflow dispatch wording kept, SPA deep-link fallback and
two-way URL sync excluded, Team RBAC M3/M6-M7 ownership recorded, alignment branches remain
unmerged, no backend/API/database/workflow change, no deployment, no Step 66C.4-P start, and the
runtime-code vs. repository-record commit distinction preserved.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RECONCILIATION_DOCS = {
    "source-of-truth-closure-record": ROOT
    / "docs"
    / "reconciliation"
    / "66m0-fe1d-sot"
    / "source-of-truth-closure-record.md",
    "merge-execution-record": ROOT
    / "docs"
    / "reconciliation"
    / "66m0-fe1d-sot"
    / "merge-execution-record.md",
}

TEAM_RBAC_DECISION = ROOT / "docs" / "decisions" / "66-team-rbac-milestone-ownership.md"
TEST_RECORD = ROOT / "docs" / "test" / "step66m0-fe1d-sot-reconciliation-merge-record.md"
SOT_RECORD = ROOT / "docs" / "design" / "66ui-source-of-truth-record.md"

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-merge"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-merge"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-merge"
    / "stage-gate-report.md",
}

MERGED_FE1D_DOCS = [
    ROOT / "docs" / "design" / "66ui4-fe1d-navigation-microcopy" / "design-brief.md",
    ROOT
    / "docs"
    / "design"
    / "66ui4-fe1d-navigation-microcopy"
    / "claude-code-technical-readiness-review.md",
    ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1d-navigation-microcopy"
    / "codex-implementation-boundary.md",
]

PROGRESS = ROOT / "source" / "progress.md"

ALL_TEXT_DOCS = {
    **RECONCILIATION_DOCS,
    "team-rbac-decision": TEAM_RBAC_DECISION,
    "test-record": TEST_RECORD,
}

DESIGN_SOURCE_COMMIT = "43269c5"
TECH_REVIEW_SOURCE_COMMIT = "25309ea"
BOUNDARY_SOURCE_COMMIT = "9e9a622"
DESIGN_MERGE_COMMIT = "45da561"
TECH_REVIEW_MERGE_COMMIT = "03318b7"
BOUNDARY_MERGE_COMMIT = "0414343"
RUNTIME_CODE_COMMIT = "513f190"
PRE_MERGE_MAIN_COMMIT = "690b700"

ALIGNMENT_BRANCH_NAMES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    combined = "\n".join(p.read_text(encoding="utf-8") for p in ALL_TEXT_DOCS.values())
    return combined + "\n" + SOT_RECORD.read_text(encoding="utf-8")


def test_reconciliation_docs_exist() -> None:
    for name, p in RECONCILIATION_DOCS.items():
        assert p.is_file(), name


def test_team_rbac_decision_exists() -> None:
    assert TEAM_RBAC_DECISION.is_file()


def test_test_record_exists() -> None:
    assert TEST_RECORD.is_file()


def test_sot_record_exists() -> None:
    assert SOT_RECORD.is_file()


def test_stage_docs_exist() -> None:
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name


def test_merged_fe1d_docs_present_on_main() -> None:
    for p in MERGED_FE1D_DOCS:
        assert p.is_file(), p


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66m0-sot-reconcile-m" in text


def test_all_three_branches_source_and_merge_commits_recorded() -> None:
    text = _norm(_all_text())
    for commit in (
        DESIGN_SOURCE_COMMIT,
        TECH_REVIEW_SOURCE_COMMIT,
        BOUNDARY_SOURCE_COMMIT,
        DESIGN_MERGE_COMMIT,
        TECH_REVIEW_MERGE_COMMIT,
        BOUNDARY_MERGE_COMMIT,
    ):
        assert commit in text, commit
    assert "merged" in text


def test_fe1d_s1_complete_shipped() -> None:
    text = _norm(_all_text())
    assert re.search(r"fe\.1d-s1[^.]{0,40}(complete|shipped)", text)


def test_fe1d_s2_unauthorized_non_critical() -> None:
    text = _norm(_all_text())
    assert re.search(r"fe\.1d-s2[^.]{0,40}(unauthorized|non-critical)", text)


def test_create_task_unchanged() -> None:
    text = _norm(_all_text())
    assert "create task" in text
    assert "unchanged" in text


def test_delivery_package_rename_deferred_to_66d() -> None:
    text = _norm(_all_text())
    assert "delivery_package_ready_for_admin_console" in text
    assert "66d" in text
    assert "defer" in text


def test_workflow_dispatch_wording_recorded() -> None:
    text = _norm(_all_text())
    assert "workflow dispatch" in text


def test_spa_deep_link_and_two_way_sync_excluded() -> None:
    text = _norm(_all_text())
    assert "spa deep-link" in text
    assert "two-way url sync" in text


def test_team_rbac_m3_m6_m7_ownership_recorded() -> None:
    text = _norm(TEAM_RBAC_DECISION.read_text(encoding="utf-8"))
    assert "approved_by_product_owner" in text
    assert "m3 owns" in text
    assert "m6/m7 own" in text


def test_alignment_branches_remain_unmerged() -> None:
    text = _norm(_all_text())
    for branch in ALIGNMENT_BRANCH_NAMES:
        assert branch in text, branch
    assert "unmerged" in text
    for path in ROOT.glob("docs/alignment/**"):
        assert not path.is_file(), path


def test_no_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term


def test_no_deployment_claimed() -> None:
    text = _norm(_all_text())
    assert "no deployment" in text or "deployment performed: no" in text


def test_step_66c4p_not_started() -> None:
    text = _norm(_all_text())
    assert "66c.4-p" in text
    assert "not started" in text


def test_runtime_and_repository_commits_distinguished() -> None:
    text = _norm(_all_text())
    assert RUNTIME_CODE_COMMIT in text
    assert PRE_MERGE_MAIN_COMMIT in text


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
    assert "STEP66M0_FE1D_SOT_RECONCILIATION_MERGE_VERIFY: PASS" in text
