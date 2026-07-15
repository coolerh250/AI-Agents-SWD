"""Step 66UI.4-FE.1A-MD -- FE.1A merge + merged-main test-deployment (docs-only checks).

This file changes no runtime code. It confirms the merge record and
merged-main test-deployment record exist and state the required facts:
PR #6/branch/merge commit, the Product Owner VISIBLE validation preceding
merge, FE.1B/FE.1C/FE.1D remaining unauthorized, that the deployment source
is merged main (not the PR branch), test-runtime-only posture, no backend/
API/database/workflow change, no production/external action, and
production_executed_true_count remaining 0.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1a-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1a-merge-record.md",
    "fe1a-merged-main-test-deployment-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1a-merged-main-test-deployment-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_pr_branch_merge_commit_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #6" in text
    assert "frontend/66ui4-fe1a-visual-polish" in text
    assert "09fe5f2" in text


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1a-md" in text


def test_product_owner_visible_referenced() -> None:
    text = _norm(_all_text())
    assert "visible" in text


def test_fe1b_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1b", "fe.1c", "fe.1d"):
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
    assert "no backend" in text or "backend changed: no" in text
    assert "no api changed" in text or "api changed: no" in text
    assert "no database changed" in text or "database changed: no" in text
    assert "no workflow changed" in text or "workflow changed: no" in text


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert "no production action" in text or "production action: no" in text
    assert "no external action" in text or "external action: no" in text


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text
    assert "remained `0" in text or "0` before and after" in text


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
    text = DOCS["fe1a-merged-main-test-deployment-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1A_MERGE_DEPLOY_VERIFY: PASS" in text
