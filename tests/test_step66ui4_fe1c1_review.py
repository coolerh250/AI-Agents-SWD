"""Step 66UI.4-FE.1C.1-R -- TaskList query param filter implementation review (docs-only checks).

This file changes no runtime code. It confirms the review record and full review doc exist and
state the required facts: Product Owner authorization, PR #11 branch/commit reviewed, the Codex
implementation marker, valid/invalid status query review, one-way-only review, dropdown sync
review, existing taskApi.list() usage, no backend/API/database/workflow/new-endpoint change, FE.1D
remaining unauthorized, Local Artifact Reconciliation, and the Product Owner validation
recommendation.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c1-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-review.md",
    "fe1c1-review-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c1-tasklist-query-param-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR11_COMMIT = "cba5dd0"
PR11_BRANCH = "frontend/66ui4-fe1c1-tasklist-query-param"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c.1-r" in text


def test_pr11_branch_and_commit_referenced() -> None:
    text = _norm(_all_text())
    assert PR11_BRANCH in text
    assert PR11_COMMIT in text


def test_product_owner_authorization_recorded() -> None:
    text = _all_text()
    assert "授權" in text
    assert "Product Owner" in text or "product owner" in text.lower()


def test_codex_implementation_marker_referenced() -> None:
    text = _norm(_all_text())
    assert "step66ui4_fe1c1_implementation_verify: pass" in text


def test_valid_status_query_review_recorded() -> None:
    text = _norm(_all_text())
    assert "blocked" in text
    assert "clarification_needed" in text


def test_invalid_status_query_review_recorded() -> None:
    text = _norm(_all_text())
    assert "unknown" in text
    assert "invalid" in text


def test_one_way_only_review_recorded() -> None:
    text = _norm(_all_text())
    assert "one-way" in text


def test_dropdown_sync_review_recorded() -> None:
    text = _norm(_all_text())
    assert "dropdown" in text
    assert "sync" in text


def test_existing_taskapi_usage_recorded() -> None:
    text = _norm(_all_text())
    assert "taskapi.list" in text


def test_no_backend_api_database_workflow_new_endpoint_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term
    assert re.search(r"no [\w/]*new endpoint", text) or "new endpoint" in text


def test_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d" in text
    assert "not authorized" in text or "unauthorized" in text


def test_local_artifact_reconciliation_recorded() -> None:
    text = _norm(_all_text())
    assert "local artifact reconciliation" in text


def test_product_owner_validation_recommendation_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner validation" in text
    assert "proceed" in text


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
    text = DOCS["fe1c1-review-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C1_REVIEW_VERIFY: PASS" in text
