"""Step 66UI.4-FE.1C-VP -- PR #10 test-runtime UI-validation preview deployment (docs-only checks).

This file changes no runtime code. It confirms the preview deployment record and UI validation
preview record exist and state the required facts: PR #10 branch/commit deployed, main not merged,
test-runtime-only scope, Product Owner validation pending, Overview attention-first behavior,
Current work 5/updated_at-desc behavior, AI team activity completed->Completed mapping, FE.1B.1
System Posture reuse, demoted metrics, placeholder-only items, the retained TaskList query-param
gap, no backend/API/database/workflow/new-endpoint change, no production/external action, FE.1D
remaining unauthorized, and Local Artifact Reconciliation recorded.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-preview-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-ui-validation-preview-deployment-record.md",
    "fe1c-ui-validation-preview": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "ui-validation-preview-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR10_COMMIT = "816856a"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c-vp" in text


def test_pr10_branch_and_commit_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #10" in text
    assert PR10_COMMIT in text


def test_main_not_merged_recorded() -> None:
    text = _norm(_all_text())
    assert "not merged" in text or "not touched" in text


def test_test_runtime_only_recorded() -> None:
    text = _norm(_all_text())
    assert "test runtime" in text


def test_product_owner_validation_pending_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner validation" in text


def test_overview_attention_first_recorded() -> None:
    text = _norm(_all_text())
    assert "attention-first" in text


def test_current_work_five_updated_at_desc_recorded() -> None:
    text = _norm(_all_text())
    assert "5" in text
    assert "updated_at" in text


def test_ai_team_activity_mapping_recorded() -> None:
    text = _norm(_all_text())
    assert "completed" in text
    assert "needs review" in text


def test_fe1b1_system_posture_reuse_recorded() -> None:
    text = _norm(_all_text())
    assert "fe.1b.1" in text
    assert "safe" in text


def test_metrics_demotion_recorded() -> None:
    text = _norm(_all_text())
    assert "demoted" in text


def test_placeholder_items_recorded() -> None:
    text = _norm(_all_text())
    assert "placeholder" in text


def test_tasklist_query_param_gap_retained() -> None:
    text = _norm(_all_text())
    assert "tasklist" in text
    assert "query-param" in text
    assert "retained" in text or "not addressed" in text


def test_no_backend_api_database_workflow_new_endpoint_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} changed: no" in text, term
    assert "new endpoint: no" in text


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
    text = DOCS["fe1c-preview-deploy-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C_PREVIEW_DEPLOY_VERIFY: PASS" in text
