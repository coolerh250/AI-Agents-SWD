"""Step 66UI.4-FE.1C.1-MD -- merge PR #11 and calibrate test runtime (docs-only checks).

This file changes no runtime code. It confirms the merge record and merged-main test deployment
record exist and state the required facts: PR #11 merge, Product Owner merge authorization,
Product Owner UI validation PASS/VISIBLE_WITH_ACCEPTED_PLATFORM_GAP, presence of the planning/
implementation/review/preview-deployment/known-gap artifacts on main, that the deployment source is
merged main, test-runtime-only scope, one-way deep-link behavior, bidirectional URL sync not
implemented, no backend/API/database/workflow/new-endpoint change, no production/external action,
FE.1D remaining unauthorized, production_executed_true_count remaining 0, Local Artifact
Reconciliation, and the secret-scan informational note.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c1-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-merge-record.md",
    "fe1c1-merged-main-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c1-merged-main-test-deployment-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR11_COMMIT = "cba5dd0"

FE1C1_ARTIFACTS = [
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-plan.md",
    ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1c1-tasklist-query-param"
    / "frontend-implementation-boundary.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c1-tasklist-query-param-planning-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-implementation-report.md",
    ROOT / "docs" / "handoffs" / "66ui4-fe1c1" / "codex-to-claude-code-handoff.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c1-tasklist-query-param-implementation-test-report.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-review.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c1-tasklist-query-param-review-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-ui-validation-preview-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c1-ui-validation-preview-deployment-record.md",
    ROOT / "docs" / "frontend" / "admin-console-spa-deep-link-fallback-known-gap.md",
    ROOT / "scripts" / "verify_step66ui4_fe1c1_planning.py",
    ROOT / "tests" / "test_step66ui4_fe1c1_planning.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c1_implementation.py",
    ROOT / "tests" / "test_step66ui4_fe1c1_implementation.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c1_review.py",
    ROOT / "tests" / "test_step66ui4_fe1c1_review.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c1_preview_deploy.py",
    ROOT / "tests" / "test_step66ui4_fe1c1_preview_deploy.py",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_fe1c1_artifacts_consolidated_on_main() -> None:
    for p in FE1C1_ARTIFACTS:
        assert p.is_file(), p


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c.1-md" in text


def test_pr11_commit_and_merge_recorded() -> None:
    text = _norm(_all_text())
    assert PR11_COMMIT in text
    assert "merged" in text


def test_product_owner_merge_authorization_recorded() -> None:
    text = _all_text()
    assert "授權" in text


def test_product_owner_validation_verdict_recorded() -> None:
    text = _norm(_all_text())
    assert "visible_with_accepted_platform_gap" in text


def test_all_stage_artifacts_referenced() -> None:
    text = _norm(_all_text())
    for path in (
        "step66ui4-fe1c1-tasklist-query-param-planning-record",
        "step66ui4-fe1c1-tasklist-query-param-implementation-test-report",
        "step66ui4-fe1c1-tasklist-query-param-review-record",
        "step66ui4-fe1c1-ui-validation-preview-deployment-record",
    ):
        assert path in text, path
    assert "known gap" in text
    assert "spa deep-link" in text


def test_deployment_source_is_merged_main() -> None:
    text = _norm(_all_text())
    assert "merged main" in text
    assert "test runtime" in text


def test_one_way_and_bidirectional_sync_recorded() -> None:
    text = _norm(_all_text())
    assert "one-way" in text or "manual dropdown" in text
    assert "bidirectional url sync" in text
    assert "not implemented" in text


def test_no_backend_api_database_workflow_new_endpoint_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term
    assert re.search(r"no [\w/]*new endpoint", text) or "new endpoint" in text


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


def test_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d" in text
    assert re.search(
        r"no [\w/]*fe\.1d authorized|fe\.1d (?:remains |is )?(?:not authorized|unauthorized)", text
    )


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text
    assert "0" in text


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
    text = DOCS["fe1c1-merged-main-deploy-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C1_MERGE_DEPLOY_VERIFY: PASS" in text
