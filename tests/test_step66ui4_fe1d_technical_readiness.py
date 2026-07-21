"""Step 66UI.4-FE.1D-TECH-REVIEW -- technical readiness review (docs-only checks).

This file changes no runtime code. It confirms the technical readiness review doc and test record
exist and state the required facts: PR #12 branch/commit, Product Owner context, the FE.1D design
marker, design-only scope, frontend-only feasibility classification, open Product Owner decisions,
recommended Codex implementation slicing, forbidden items, the SPA deep-link fallback exclusion, no
backend/API/database/workflow/new-endpoint change, Codex and FE.1D implementation remaining
unauthorized, Local Artifact Reconciliation, and no Windows/local path exposure.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1d-tech-readiness-review": ROOT
    / "docs"
    / "design"
    / "66ui4-fe1d-navigation-microcopy"
    / "claude-code-technical-readiness-review.md",
    "fe1d-tech-readiness-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1d-technical-readiness-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR12_COMMIT = "43269c5"
PR12_BRANCH = "design/66ui4-fe1d-navigation-microcopy"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1d-tech-review" in text


def test_pr12_branch_and_commit_recorded() -> None:
    text = _norm(_all_text())
    assert PR12_BRANCH in text
    assert PR12_COMMIT in text


def test_product_owner_context_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner context" in text


def test_design_marker_referenced() -> None:
    text = _norm(_all_text())
    assert "design66ui4_fe1d_navigation_microcopy_verify: pass" in text


def test_design_only_scope_recorded() -> None:
    text = _norm(_all_text())
    assert "design-only scope" in text


def test_feasibility_classification_recorded() -> None:
    text = _norm(_all_text())
    assert "feasibility classification" in text
    for area in ("navigation labels", "status label map", "relative time"):
        assert area in text, area


def test_open_decisions_recorded() -> None:
    text = _norm(_all_text())
    assert "open product owner decision" in text or "open decisions" in text
    assert "new task" in text
    assert "create task" in text


def test_implementation_slicing_recorded() -> None:
    text = _norm(_all_text())
    assert "implementation slicing" in text
    assert "slice 1" in text


def test_forbidden_items_recorded() -> None:
    text = _norm(_all_text())
    assert "forbidden items" in text or "forbidden item" in text


def test_spa_deep_link_fallback_excluded() -> None:
    text = _norm(_all_text())
    assert "spa deep-link" in text
    assert "known gap" in text or "known platform gap" in text


def test_no_backend_api_database_workflow_new_endpoint_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term
    assert re.search(r"no [\w/]*new endpoint", text) or "new endpoint" in text


def test_codex_unauthorized() -> None:
    text = _norm(_all_text())
    assert "codex" in text
    assert "codex remains unauthorized" in text or "unauthorized" in text


def test_fe1d_implementation_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d implementation" in text
    assert "remains unauthorized" in text


def test_task_statuses_correction_recorded() -> None:
    text = _norm(_all_text())
    assert "authoritative" in text
    assert "task_statuses" in text
    for status in ("submitted", "failed", "accepted", "rejected", "archived"):
        assert status in text, status


def test_local_artifact_reconciliation_recorded() -> None:
    text = _norm(_all_text())
    assert "local artifact reconciliation" in text


def test_overall_verdict_recorded() -> None:
    text = _norm(_all_text())
    assert "pass_with_gaps" in text


def test_no_local_windows_paths_committed() -> None:
    windows_path_shape = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)
    for name, p in DOCS.items():
        assert not windows_path_shape.search(p.read_text(encoding="utf-8")), name


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    text = _all_text().lower()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_marker_pass_present() -> None:
    text = DOCS["fe1d-tech-readiness-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1D_TECHNICAL_READINESS_VERIFY: PASS" in text
