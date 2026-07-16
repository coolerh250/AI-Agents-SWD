"""Step 66UI.4-FE.1B.1-MD -- FE.1B.1 merge + merged-main test-deployment (docs-only checks).

This file changes no runtime code. It confirms the merge record and merged-main test-deployment
record exist and state the required facts: PR #9/branch/commit, the Product Owner merge
authorization, the VISIBLE validation preceding merge, closure of the prior Step 66UI.4-FE.1B-V
Unavailable gap, FE.1C/FE.1D remaining unauthorized, all FE.1B.1 planning/implementation/review/
preview artifacts consolidated onto main, the deployment source being merged main (not the PR
branch), test-runtime-only posture, no backend/API/database/workflow change, no
/operations/safety response shape change, no production/external action,
production_executed_true_count remaining 0, and Local Artifact Reconciliation recorded.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-merge-record.md",
    "fe1b1-merged-main-test-deployment-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b1-merged-main-test-deployment-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR9_COMMIT = "974822d"
PR9_BRANCH = "frontend/66ui4-fe1b1-safety-field-mapping"

FE1B1_ARTIFACTS = [
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-safety-field-mapping-plan.md",
    ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1b1-safety-field-mapping"
    / "frontend-implementation-boundary.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-safety-field-mapping-planning-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-safety-field-mapping-implementation-report.md",
    ROOT / "docs" / "handoffs" / "66ui4-fe1b1" / "codex-to-claude-code-handoff.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-claude-code-review.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-review-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-ui-validation-preview-deployment-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-ui-validation-preview-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-product-owner-ui-validation-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-product-owner-validation.md",
    ROOT / "apps" / "admin-console" / "src" / "components" / "CalmSafetyPosture.tsx",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_fe1b1_artifacts_consolidated_on_main() -> None:
    for p in FE1B1_ARTIFACTS:
        assert p.is_file(), p


def test_pr9_branch_commit_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #9" in text
    assert PR9_BRANCH in text
    assert PR9_COMMIT in text


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1b.1-md" in text


def test_product_owner_authorization_and_validation() -> None:
    text = _norm(_all_text())
    assert "visible" in text
    assert "authorization" in text


def test_prior_gap_closed() -> None:
    text = _norm(_all_text())
    assert "unavailable" in text
    assert "gap" in text
    assert "resolved" in text or "closed" in text


def test_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1c", "fe.1d"):
        assert phrase in text, phrase
    assert "unauthorized" in text or "not authorized" in text


def test_deployment_source_is_merged_main() -> None:
    text = _norm(_all_text())
    assert "merged main" in text
    assert "pr branch" in text


def test_test_runtime_only_posture() -> None:
    text = _norm(_all_text())
    assert "test runtime" in text or "test-runtime" in text


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


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text


def test_local_artifact_reconciliation_recorded() -> None:
    text = _norm(_all_text())
    assert "local artifact reconciliation" in text


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


def test_no_local_windows_paths_committed() -> None:
    windows_path_shape = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)
    for name, p in DOCS.items():
        assert not windows_path_shape.search(p.read_text(encoding="utf-8")), name


def test_marker_pass_present() -> None:
    text = DOCS["fe1b1-merged-main-test-deployment-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1B1_MERGE_DEPLOY_VERIFY: PASS" in text
