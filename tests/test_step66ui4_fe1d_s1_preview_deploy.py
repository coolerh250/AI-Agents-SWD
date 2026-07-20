"""Step 66UI.4-FE.1D-S1-VP -- PR #13 test runtime UI validation preview deployment (docs-only
checks).

This file changes no runtime code. It confirms the preview deployment record and UI validation
preview record exist and state the required facts: PR #13 branch/commit, main not merged, test-
runtime-only scope, Product Owner validation pending, 7 nav groups and subtitles, Soon/Read-only/
Evidence badges, Platform Ops compact density, Delivery Package under Platform Ops, route
preservation, no fake controls, Slice 2 not implemented, Product Owner decisions preserved, SPA
deep-link fallback and two-way URL sync excluded, no backend/API/database/workflow/new-endpoint/
new-route change, no production/external action, FE.1D Slice 2 remaining unauthorized, and Local
Artifact Reconciliation.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1d-s1-preview-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1d-s1-ui-validation-preview-deployment-record.md",
    "fe1d-s1-ui-validation-preview-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-ui-validation-preview-record.md",
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
    assert "66ui.4-fe.1d-s1-vp" in text


def test_pr13_branch_and_commit_recorded() -> None:
    text = _norm(_all_text())
    assert PR13_BRANCH in text
    assert PR13_COMMIT in text


def test_main_not_merged_recorded() -> None:
    text = _norm(_all_text())
    assert re.search(r"main[^.]*not[^.]*merged|main was not merged|main not merged", text)


def test_test_runtime_only_scope_recorded() -> None:
    text = _norm(_all_text())
    assert "test runtime only" in text or "test-runtime only" in text


def test_po_validation_pending_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner validation" in text
    assert "pending" in text


def test_nav_groups_and_subtitles_recorded() -> None:
    text = _norm(_all_text())
    assert re.search(r"7 (navigation|nav) groups", text)
    assert "group subtitle" in text


def test_badges_recorded() -> None:
    text = _norm(_all_text())
    for badge in ("soon", "read-only", "evidence"):
        assert badge in text, badge


def test_platform_ops_and_delivery_package_recorded() -> None:
    text = _norm(_all_text())
    assert "platform ops" in text
    assert "delivery package" in text
    assert "compact density" in text


def test_route_preservation_and_no_fake_controls_recorded() -> None:
    text = _norm(_all_text())
    assert "route" in text and "preserved" in text
    assert "fake control" in text


def test_slice2_not_implemented_and_unauthorized() -> None:
    text = _norm(_all_text())
    assert "slice 2" in text
    assert "remains unauthorized" in text


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


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


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
    text = DOCS["fe1d-s1-preview-deploy-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1D_S1_PREVIEW_DEPLOY_VERIFY: PASS" in text
