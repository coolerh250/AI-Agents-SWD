"""Step 66UI.4-FE.1B.1-V -- Product Owner UI validation (docs-only checks).

This file changes no runtime code. It confirms the validation record and test report exist and
state the required facts: PR #9/branch/commit, the VISIBLE verdict, resolution of the prior
FE.1B-V accepted Unavailable gap, the compact-vs-full per-task approval wording clarification
(not a regression), production_executed_true_count remaining 0, no production/external/workflow
action claimed, FE.1C/FE.1D still unauthorized, and that merge authorization is not granted.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-product-owner-ui-validation-record.md",
    "fe1b1-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b1-product-owner-validation.md",
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
    assert "66ui.4-fe.1b.1-v" in text


def test_visible_verdict_recorded() -> None:
    text = _norm(_all_text())
    assert "visible" in text


def test_prior_gap_resolved() -> None:
    text = _norm(_all_text())
    assert "resolved" in text
    assert "unavailable" in text


def test_per_task_approval_clarification_recorded() -> None:
    text = _norm(_all_text())
    assert "compact" in text
    assert "per-task" in text
    assert "not a regression" in text or "not touched" in text


def test_production_executed_true_count_recorded() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert "no production action" in text or "production action: no" in text
    assert "no external action" in text or "external action: no" in text
    assert "workflow dispatch" in text


def test_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1c", "fe.1d"):
        assert phrase in text, phrase
    assert "unauthorized" in text or "not authorized" in text


def test_pr_not_merged() -> None:
    text = _norm(_all_text())
    assert "does not merge" in text or "not merged" in text
    assert "merge authorization" in text


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
    text = DOCS["fe1b1-product-owner-validation"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1B1_PRODUCT_OWNER_VALIDATION_VERIFY: PASS" in text
