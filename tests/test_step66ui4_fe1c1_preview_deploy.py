"""Step 66UI.4-FE.1C.1-VP -- PR #11 test-runtime UI-validation preview deployment (docs-only).

This file changes no runtime code. It confirms the preview deployment record and UI validation
preview record exist and state the required facts: PR #11 branch/commit deployed, main not merged,
test-runtime-only scope, Product Owner validation pending, /tasks?status=blocked and
/tasks?status=clarification_needed behavior, invalid status query behavior, manual dropdown not
updating the URL, bidirectional URL sync not implemented, no backend/API/database/workflow/new-
endpoint change, no production/external action, FE.1D remaining unauthorized, and Local Artifact
Reconciliation recorded.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c1-preview-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c1-ui-validation-preview-deployment-record.md",
    "fe1c1-ui-validation-preview": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-ui-validation-preview-record.md",
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
    assert "66ui.4-fe.1c.1-vp" in text


def test_pr11_branch_and_commit_referenced() -> None:
    text = _norm(_all_text())
    assert PR11_BRANCH in text
    assert PR11_COMMIT in text


def test_main_not_merged_recorded() -> None:
    text = _norm(_all_text())
    assert "not merged" in text or "not touched" in text


def test_test_runtime_only_recorded() -> None:
    text = _norm(_all_text())
    assert "test runtime" in text


def test_product_owner_validation_pending_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner validation" in text


def test_blocked_and_clarification_needed_behavior_recorded() -> None:
    text = _norm(_all_text())
    assert "status=blocked" in text
    assert "status=clarification_needed" in text


def test_invalid_status_query_behavior_recorded() -> None:
    text = _norm(_all_text())
    assert "invalid" in text
    assert "unknown" in text or "falls back" in text or "fall back" in text


def test_manual_dropdown_url_behavior_recorded() -> None:
    text = _norm(_all_text())
    assert "manual dropdown" in text
    assert "url" in text


def test_bidirectional_url_sync_not_implemented_recorded() -> None:
    text = _norm(_all_text())
    assert "bidirectional url sync" in text
    assert "not implemented" in text


def test_no_backend_api_database_workflow_new_endpoint_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} changed: no" in text, term
    assert "new endpoint: no" in text or re.search(r"no [\w/]*new endpoint", text)


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text) or "production action: no" in text
    assert re.search(r"no [\w/]*external action", text) or "external action: no" in text


def test_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d" in text
    assert "not authorized" in text or "unauthorized" in text


def test_local_artifact_reconciliation_recorded() -> None:
    text = _norm(_all_text())
    assert "local artifact reconciliation" in text


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
    text = DOCS["fe1c1-preview-deploy-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C1_PREVIEW_DEPLOY_VERIFY: PASS" in text
