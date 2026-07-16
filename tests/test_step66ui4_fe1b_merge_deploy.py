"""Step 66UI.4-FE.1B-MD -- FE.1B merge + merged-main test-deployment (docs-only checks).

This file changes no runtime code. It confirms the merge record and
merged-main test-deployment record exist and state the required facts:
PR #7/branch/merge commit, the Product Owner VISIBLE-with-accepted-gap
validation preceding merge, the Safety badge Unavailable accepted gap,
FE.1C/FE.1D remaining unauthorized, FE.1B.1 being recommended but not
implemented, the deployment source being merged main (not the PR branch),
test-runtime-only posture, no backend/API/database/workflow change, no
production/external action, and production_executed_true_count remaining 0.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b-merge-record.md",
    "fe1b-merged-main-test-deployment-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b-merged-main-test-deployment-record.md",
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
    assert "pr #7" in text
    assert "frontend/66ui4-fe1b-calm-safety" in text
    assert "5a2bc4e" in text


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1b-md" in text


def test_product_owner_visible_with_accepted_gap() -> None:
    text = _norm(_all_text())
    assert "visible" in text
    assert "accepted" in text


def test_safety_badge_unavailable_gap_recorded() -> None:
    text = _norm(_all_text())
    assert "dispatch_enabled" in text
    assert "approval_required" in text
    assert "unavailable" in text


def test_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1c", "fe.1d"):
        assert phrase in text, phrase
    assert "unauthorized" in text or "not authorized" in text


def test_fe1b1_recommended_not_implemented() -> None:
    text = _norm(_all_text())
    assert "fe.1b.1" in text
    assert "not fixed" in text or "not implemented" in text


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


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


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
    text = DOCS["fe1b-merged-main-test-deployment-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1B_MERGE_DEPLOY_VERIFY: PASS" in text
