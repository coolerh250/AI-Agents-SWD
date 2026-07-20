"""Step 66UI.4-FE.1D-S1-POV -- Product Owner UI validation record (docs-only checks).

This file changes no runtime code. It confirms the Product Owner validation doc and test record
exist and state the required facts: the Product Owner validation result (PASS), PR #13 branch/
commit, the preview deployment record reference, the 12-item checklist accepted as PASS, main not
merged yet, merge authorization still required, FE.1D Slice 2 remaining unauthorized, no backend/
API/database/workflow change, no endpoint/route change, SPA deep-link fallback and two-way URL sync
excluded, "+ Create task" unchanged, delivery_package_ready_for_admin_console unchanged/deferred,
and production_executed_true_count remaining 0.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1d-s1-po-validation": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-product-owner-validation.md",
    "fe1d-s1-po-validation-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1d-s1-product-owner-validation-record.md",
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
    assert "66ui.4-fe.1d-s1-pov" in text


def test_pr13_branch_and_commit_recorded() -> None:
    text = _norm(_all_text())
    assert PR13_BRANCH in text
    assert PR13_COMMIT in text


def test_product_owner_pass_result_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner ui validation" in text
    assert "pass" in text


def test_preview_deployment_referenced() -> None:
    text = _norm(_all_text())
    assert "preview deployment record" in text or "preview deploy" in text


def test_checklist_acceptance_recorded() -> None:
    text = _norm(_all_text())
    assert re.search(r"12[- ]item checklist", text) or "all 12" in text


def test_main_not_merged_and_authorization_required() -> None:
    text = _norm(_all_text())
    assert re.search(r"main[^.]*not[^.]*merged|main not merged", text)
    assert "merge authorization" in text
    assert "still required" in text


def test_slice2_unauthorized() -> None:
    text = _norm(_all_text())
    assert "slice 2" in text
    assert "remains unauthorized" in text


def test_no_backend_api_database_workflow_new_endpoint_route_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term
    assert re.search(r"no [\w/]*new endpoint", text) or "new endpoint" in text
    assert re.search(r"no [\w/]*new route", text) or "new route" in text


def test_spa_deep_link_and_two_way_sync_excluded() -> None:
    text = _norm(_all_text())
    assert "spa deep-link" in text
    assert "two-way url sync" in text


def test_po_decisions_preserved_recorded() -> None:
    text = _norm(_all_text())
    assert "create task" in text
    assert "delivery_package_ready_for_admin_console" in text


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text
    assert "0" in text


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
    text = DOCS["fe1d-s1-po-validation-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1D_S1_PRODUCT_OWNER_VALIDATION_VERIFY: PASS" in text
