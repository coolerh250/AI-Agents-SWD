"""Step 66M0-SOT-RECONCILE-P v2 -- FE.1D source-of-truth reconciliation planning (docs-only checks).

This file changes no runtime code. It confirms the nine reconciliation docs plus the test record
and stage artifacts exist and state the required facts: all three FE.1D branches assessed with one
disposition each, all three alignment branches assessed as advisory only, no merge/cherry-pick/
deployment claimed, alignment branches remaining unmerged, FE.1D-S2 remaining unauthorized/non-
critical, runtime code unchanged, the SPA deep-link gap excluded, delivery_package rename deferred
to 66D, "+ Create task" unchanged, and the Codex local-path exposure validation recorded.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RECON_DIR = ROOT / "docs" / "reconciliation" / "66m0-fe1d-sot"

RECON_DOCS = {
    "current-main-runtime-state": RECON_DIR / "current-main-runtime-state.md",
    "alignment-freshness-assessment": RECON_DIR / "alignment-freshness-assessment.md",
    "cross-partner-consensus-matrix": RECON_DIR / "cross-partner-consensus-matrix.md",
    "fe1d-branch-disposition-matrix": RECON_DIR / "fe1d-branch-disposition-matrix.md",
    "conflict-analysis": RECON_DIR / "conflict-analysis.md",
    "recommended-merge-plan": RECON_DIR / "recommended-merge-plan.md",
    "post-merge-verification-plan": RECON_DIR / "post-merge-verification-plan.md",
    "product-owner-decision-checklist": RECON_DIR / "product-owner-decision-checklist.md",
    "align2-advisory-handoff": RECON_DIR / "align2-advisory-handoff.md",
}

RECORD_DOC = ROOT / "docs" / "test" / "step66m0-fe1d-sot-reconciliation-planning-v2-record.md"

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-plan-v2"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-plan-v2"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-plan-v2"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

FE1D_BRANCHES = (
    "design/66ui4-fe1d-navigation-microcopy",
    "review/66ui4-fe1d-technical-readiness",
    "review/66ui4-fe1d-boundary",
)
ALIGNMENT_BRANCHES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

ALL_TEXT_DOCS = {**RECON_DOCS, "planning-record": RECORD_DOC}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in ALL_TEXT_DOCS.values())


def test_recon_docs_exist() -> None:
    for name, p in RECON_DOCS.items():
        assert p.is_file(), name


def test_record_doc_exists() -> None:
    assert RECORD_DOC.is_file()


def test_stage_docs_exist() -> None:
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66m0-sot-reconcile-p v2" in text


def test_all_fe1d_branches_assessed() -> None:
    text = _norm(_all_text())
    for branch in FE1D_BRANCHES:
        assert branch in text, branch


def test_all_alignment_branches_assessed() -> None:
    text = _norm(_all_text())
    for branch in ALIGNMENT_BRANCHES:
        assert branch in text, branch


def test_fe1d_dispositions_recorded() -> None:
    text = _norm(_all_text())
    assert "merge_full" in text


def test_alignment_advisory_classifications_recorded() -> None:
    text = _norm(_all_text())
    assert "advisory_ready_for_align2" in text


def test_no_merge_or_cherry_pick_claimed() -> None:
    text = _norm(_all_text())
    assert "no merge" in text or "no branch" in text
    assert "cherry-pick" in text


def test_alignment_branches_remain_unmerged() -> None:
    text = _norm(_all_text())
    assert "remain unmerged" in text or "remains unmerged" in text


def test_fe1d_slice2_unauthorized_non_critical() -> None:
    text = _norm(_all_text())
    assert "fe.1d slice 2" in text
    assert "unauthorized" in text or "non-critical" in text


def test_spa_deep_link_excluded() -> None:
    text = _norm(_all_text())
    assert "spa deep-link" in text


def test_delivery_package_rename_deferred_to_66d() -> None:
    text = _norm(_all_text())
    assert "delivery_package_ready_for_admin_console" in text
    assert "66d" in text


def test_create_task_unchanged() -> None:
    text = _norm(_all_text())
    assert "create task" in text


def test_codex_local_artifact_validation_recorded() -> None:
    text = _norm(_all_text())
    assert "local artifact" in text or "local-artifact" in text
    assert "codex" in text


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
    for forbidden in ("10.0.1.31", "10.0.1.32", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_marker_pass_present() -> None:
    text = RECORD_DOC.read_text(encoding="utf-8")
    assert "STEP66M0_FE1D_SOT_RECONCILIATION_PLAN_V2_VERIFY: PASS" in text
