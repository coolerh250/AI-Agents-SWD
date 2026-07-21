"""Step 66ALIGN.2-CONSOLIDATE -- project completion master plan consolidation (docs-only checks).

This file changes no runtime code. It confirms the 11 consolidated Master Plan documents, the test
record, and stage artifacts exist and state the required facts: M0 CLOSED, M1-M7 status recorded,
Step 66C.4-P next but not started, 66D-ARCH preceding Delivery UI implementation, FE.1D-S2
unauthorized/non-critical, Team RBAC M3/M6-M7 ownership recorded, the no-fake-UI/capability
principle recorded, alignment branches remaining unmerged, no runtime/backend/API/database/workflow
change or deployment claimed, and source/progress.md updated.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "docs" / "alignment" / "66-project-completion" / "master"

MASTER_DOCS = {
    "master-plan": MASTER_DIR / "project-completion-master-plan.md",
    "canonical-milestone-manifest": MASTER_DIR / "canonical-milestone-manifest.md",
    "current-state-capability-matrix": MASTER_DIR / "current-state-capability-matrix.md",
    "critical-path-and-dependency-map": MASTER_DIR / "critical-path-and-dependency-map.md",
    "role-ownership-matrix": MASTER_DIR / "role-ownership-matrix.md",
    "product-and-technical-gates": MASTER_DIR / "product-and-technical-gates.md",
    "project-definition-of-done": MASTER_DIR / "project-definition-of-done.md",
    "deferred-work-register": MASTER_DIR / "deferred-work-register.md",
    "next-executable-stage-sequence": MASTER_DIR / "next-executable-stage-sequence.md",
    "cross-partner-resolution-record": MASTER_DIR / "cross-partner-resolution-record.md",
    "product-owner-review-checklist": MASTER_DIR / "product-owner-review-checklist.md",
}

TEST_RECORD = ROOT / "docs" / "test" / "step66align2-project-completion-master-plan-record.md"

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"
ALIGNMENT_ROOT = ROOT / "docs" / "alignment" / "66-project-completion"
FORBIDDEN_ORIGINAL_DIRS = ("claude-code", "claude-design", "codex")

ALIGNMENT_BRANCH_NAMES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

ALL_TEXT_DOCS = {**MASTER_DOCS, "test-record": TEST_RECORD}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in ALL_TEXT_DOCS.values())


def test_master_docs_exist() -> None:
    for name, p in MASTER_DOCS.items():
        assert p.is_file(), name


def test_test_record_exists() -> None:
    assert TEST_RECORD.is_file()


def test_stage_docs_exist() -> None:
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name


def test_original_partner_dirs_not_copied_into_scope() -> None:
    for sub in FORBIDDEN_ORIGINAL_DIRS:
        original_dir = ALIGNMENT_ROOT / sub
        assert not (original_dir.is_dir() and any(original_dir.iterdir())), original_dir


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66align.2-consolidate" in text


def test_m0_closed_recorded() -> None:
    text = _norm(_all_text())
    assert re.search(r"m0[^.]{0,20}closed", text)


def test_m1_through_m7_status_recorded() -> None:
    text = _norm(_all_text())
    for m in ("m1", "m2", "m3", "m4", "m5", "m6", "m7"):
        assert m + " —" in text or m + " -" in text or m + ":" in text, m
    assert "in_progress" in text
    assert "not_started" in text


def test_step_66c4p_next_but_not_started() -> None:
    text = _norm(_all_text())
    assert "66c.4-p" in text
    assert "not started" in text or "not_started" in text


def test_66d_arch_precedes_delivery_ui() -> None:
    text = _norm(_all_text())
    assert "66d-arch" in text
    assert "66d-design" in text
    assert re.search(r"66d-arch.{0,400}66d-design", text, re.DOTALL) or "before any ui" in text


def test_fe1d_s2_unauthorized_non_critical() -> None:
    text = _norm(_all_text())
    assert re.search(r"fe\.1d-s2[^.]{0,60}(unauthorized|non-critical)", text)


def test_team_rbac_m3_and_m6_m7_ownership_recorded() -> None:
    text = _norm(_all_text())
    assert "m3 owns" in text
    assert "m6/m7 own" in text


def test_no_fake_ui_capability_principle_recorded() -> None:
    text = _norm(_all_text())
    fake_ui_cues = (
        "fake delivery inbox",
        "fake action center",
        "fake notification",
        "fabricated agent activity",
        "orchestration controls that do not exist",
    )
    assert any(cue in text for cue in fake_ui_cues)


def test_alignment_branches_remain_unmerged() -> None:
    text = _norm(_all_text())
    for branch in ALIGNMENT_BRANCH_NAMES:
        assert branch in text, branch
    assert "unmerged" in text


def test_no_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term


def test_no_deployment_claimed() -> None:
    text = _norm(_all_text())
    assert "no deployment" in text


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
    assert "STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_VERIFY: PASS" in text
