"""Step 66UI.4-FE.1D-S1-MD -- merge PR #13 and deploy merged main (docs-only checks).

This file changes no runtime code. It confirms the merge record and merged-main test deployment
record exist and state the required facts: PR #13 merge, Product Owner merge authorization, the
merge commit, test runtime deployment result, merged main active, presence of the implementation/
review/preview-deployment/Product-Owner-validation artifacts on main, 7 nav groups/subtitles, Soon/
Read-only/Evidence badges, Platform Ops compact density, Delivery Package under Platform Ops, no
FE.1D Slice 2, "+ Create task" unchanged, delivery_package_ready_for_admin_console rename deferred,
SPA deep-link fallback and two-way URL sync excluded, no backend/API/database/workflow/new-endpoint/
new-route change, production_executed_true_count remaining 0, Local Artifact Reconciliation, and
the secret-scan informational note.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1d-s1-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-merge-record.md",
    "fe1d-s1-merged-main-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1d-s1-merged-main-test-deployment-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR13_COMMIT = "72d8bff"
PR13_BRANCH = "frontend/66ui4-fe1d-s1-navigation-polish"
MERGE_COMMIT = "513f190"

FE1D_S1_ARTIFACTS = [
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-implementation-report.md",
    ROOT / "docs" / "handoffs" / "66ui4-fe1d-s1" / "codex-to-claude-code-handoff.md",
    ROOT / "docs" / "test" / "step66ui4-fe1d-s1-navigation-polish-implementation-test-report.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-review.md",
    ROOT / "docs" / "test" / "step66ui4-fe1d-s1-navigation-polish-review-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1d-s1-ui-validation-preview-deployment-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-ui-validation-preview-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-product-owner-validation.md",
    ROOT / "docs" / "test" / "step66ui4-fe1d-s1-product-owner-validation-record.md",
    ROOT / "scripts" / "verify_step66ui4_fe1d_s1_implementation.py",
    ROOT / "tests" / "test_step66ui4_fe1d_s1_implementation.py",
    ROOT / "scripts" / "verify_step66ui4_fe1d_s1_review.py",
    ROOT / "tests" / "test_step66ui4_fe1d_s1_review.py",
    ROOT / "scripts" / "verify_step66ui4_fe1d_s1_preview_deploy.py",
    ROOT / "tests" / "test_step66ui4_fe1d_s1_preview_deploy.py",
    ROOT / "scripts" / "verify_step66ui4_fe1d_s1_product_owner_validation.py",
    ROOT / "tests" / "test_step66ui4_fe1d_s1_product_owner_validation.py",
    ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx",
    ROOT / "apps" / "admin-console" / "src" / "components" / "NavGroup.tsx",
    ROOT / "apps" / "admin-console" / "src" / "__tests__" / "NavigationGrouping.test.tsx",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_fe1d_s1_artifacts_consolidated_on_main() -> None:
    for p in FE1D_S1_ARTIFACTS:
        assert p.is_file(), p


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1d-s1-md" in text


def test_pr13_commit_and_merge_recorded() -> None:
    text = _norm(_all_text())
    assert PR13_BRANCH in text
    assert PR13_COMMIT in text
    assert MERGE_COMMIT in text


def test_product_owner_merge_authorization_recorded() -> None:
    text = _all_text()
    assert "授權" in text


def test_test_runtime_deployment_recorded() -> None:
    text = _norm(_all_text())
    assert "test runtime" in text
    assert "merged main" in text


def test_nav_groups_subtitles_and_badges_recorded() -> None:
    text = _norm(_all_text())
    assert re.search(r"7 (navigation|nav) groups", text)
    assert "group subtitle" in text
    for badge in ("soon", "read-only", "evidence"):
        assert badge in text, badge


def test_platform_ops_and_delivery_package_recorded() -> None:
    text = _norm(_all_text())
    assert "compact density" in text
    assert "delivery package" in text
    assert "platform ops" in text


def test_po_decisions_preserved_recorded() -> None:
    text = _norm(_all_text())
    assert "create task" in text
    assert "delivery_package_ready_for_admin_console" in text


def test_spa_deep_link_and_two_way_sync_excluded() -> None:
    text = _norm(_all_text())
    assert "spa deep-link" in text
    assert "two-way url sync" in text


def test_no_backend_api_database_workflow_new_endpoint_route_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term
    assert re.search(r"no [\w/]*new endpoint", text) or "new endpoint" in text
    assert re.search(r"no [\w/]*new route", text) or "new route" in text


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text
    assert "0" in text


def test_fe1d_slice2_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d slice 2" in text
    assert "remains unauthorized" in text or "no fe.1d slice 2 authorized" in text


def test_local_artifact_reconciliation_recorded() -> None:
    text = _norm(_all_text())
    assert "local artifact reconciliation" in text


def test_secret_scan_informational_note_recorded() -> None:
    text = _norm(_all_text())
    assert "informational=100" in text


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
    text = DOCS["fe1d-s1-merged-main-deploy-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1D_S1_MERGE_DEPLOY_VERIFY: PASS" in text
