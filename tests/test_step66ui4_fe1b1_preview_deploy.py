"""Step 66UI.4-FE.1B.1-VP -- PR #9 test runtime UI validation preview deployment (docs-only checks).

This file changes no runtime code. It confirms the preview deployment record and UI validation
preview record exist and state the required facts: PR #9 branch/commit, main not merged, test
runtime only, Product Owner validation pending, Safety badge observed state, raw evidence/details,
retired-field behavior, approval wording behavior, production_executed_true_count before/after, no
backend/API/database/workflow change, /operations/safety response shape unchanged, no production/
external action, FE.1C/FE.1D unauthorized, Local Artifact Reconciliation recorded, and no local
absolute path exposure.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-preview-deployment-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b1-ui-validation-preview-deployment-record.md",
    "fe1b1-ui-validation-preview-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-ui-validation-preview-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR9_COMMIT = "974822d"
PR9_BRANCH = "frontend/66ui4-fe1b1-safety-field-mapping"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_pr9_branch_commit_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #9" in text
    assert PR9_BRANCH in text
    assert PR9_COMMIT in text


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1b.1-vp" in text


def test_main_not_merged() -> None:
    text = _norm(_all_text())
    assert re.search(r"main\W*not merged", text)


def test_test_runtime_only() -> None:
    text = _norm(_all_text())
    assert "test runtime" in text


def test_product_owner_validation_pending() -> None:
    text = _norm(_all_text())
    assert "product owner" in text
    assert "pending" in text


def test_safety_badge_observed_state() -> None:
    text = _norm(_all_text())
    assert "safety badge" in text
    assert "safe" in text


def test_raw_evidence_details_recorded() -> None:
    text = _norm(_all_text())
    assert "evidence" in text
    assert "accessible" in text or "expandable" in text


def test_retired_fields_behavior_recorded() -> None:
    text = _norm(_all_text())
    assert "not applicable at this endpoint" in text


def test_approval_wording_behavior_recorded() -> None:
    text = _norm(_all_text())
    assert "per-task" in text or "per task" in text


def test_production_executed_true_count_before_after() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text
    assert "before and after" in text or "before/after" in text


def test_no_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text), term


def test_response_shape_unchanged() -> None:
    text = _norm(_all_text())
    assert "/operations/safety" in text
    assert "response shape" in text


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


def test_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1c", "fe.1d"):
        assert phrase in text, phrase
    assert "unauthorized" in text or "not authorized" in text


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
    text = DOCS["fe1b1-preview-deployment-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1B1_PREVIEW_DEPLOY_VERIFY: PASS" in text
