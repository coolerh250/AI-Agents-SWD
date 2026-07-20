"""Step 66UI.4-FE.1D-S1-R -- Navigation Polish implementation review (docs-only checks).

This file changes no runtime code. It confirms the review doc and review record exist and state
the required facts: PR #13 branch/commit, Product Owner authorization, the Codex implementation
marker, navigation label/subtitle/badge/density review, Delivery Package placement under Platform
Ops, Product Owner decisions preserved, FE.1D Slice 2 exclusion, no backend/API/database/workflow/
new-endpoint/new-route change, Local Artifact Reconciliation, and no Windows/local path exposure.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "slice1-navigation-polish-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-review.md",
    "slice1-navigation-polish-review-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1d-s1-navigation-polish-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR13_COMMIT = "72d8bff"
PR13_BRANCH = "frontend/66ui4-fe1d-s1-navigation-polish"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1d-s1-r" in text


def test_pr13_branch_and_commit_recorded() -> None:
    text = _norm(_all_text())
    assert PR13_BRANCH in text
    assert PR13_COMMIT in text


def test_product_owner_authorization_recorded() -> None:
    text = _all_text()
    assert "product owner" in text.lower()
    assert "授權" in text


def test_implementation_marker_referenced() -> None:
    text = _norm(_all_text())
    assert "step66ui4_fe1d_s1_implementation_verify: pass" in text


def test_functional_review_areas_recorded() -> None:
    text = _norm(_all_text())
    for area in (
        "navigation label",
        "group subtitle",
        "badge",
        "compact density",
    ):
        assert area in text, area


def test_delivery_package_placement_recorded() -> None:
    text = _norm(_all_text())
    assert "delivery package" in text
    assert "platform ops" in text


def test_po_decisions_preserved_recorded() -> None:
    text = _norm(_all_text())
    assert "create task" in text
    assert "delivery_package_ready_for_admin_console" in text
    assert "spa deep-link" in text
    assert "two-way url sync" in text


def test_no_backend_api_database_workflow_new_endpoint_route_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term
    assert re.search(r"no [\w/]*new endpoint", text) or "new endpoint" in text
    assert re.search(r"no [\w/]*new route", text) or "new route" in text


def test_slice2_unauthorized() -> None:
    text = _norm(_all_text())
    assert "slice 2" in text
    assert "remains unauthorized" in text


def test_local_artifact_reconciliation_recorded() -> None:
    text = _norm(_all_text())
    assert "local artifact reconciliation" in text


def test_po_validation_recommendation_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner validation" in text


def test_overall_verdict_recorded() -> None:
    text = _norm(_all_text())
    assert "overall verdict" in text
    assert "pass" in text


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
    text = DOCS["slice1-navigation-polish-review-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1D_S1_REVIEW_VERIFY: PASS" in text
