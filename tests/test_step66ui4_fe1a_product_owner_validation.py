"""Step 66UI.4-FE.1A-V -- Product Owner UI validation (docs-only checks).

Validation stage: this file itself changes no runtime code. It confirms
the validation record docs exist and state the required facts: PR #6/
branch/commit, the VISIBLE verdict, production_executed_true_count=0,
no production/external/workflow action, FE.1B/FE.1C/FE.1D remaining
unauthorized, and no merge performed/authorized by this document.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "fe1a-product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1a-product-owner-ui-validation-record.md",
    "fe1a-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1a-product-owner-validation.md",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


def test_pr_branch_commit_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #6" in text
    assert "frontend/66ui4-fe1a-visual-polish" in text
    assert "7e6422f" in text


def test_visible_verdict_recorded() -> None:
    text = _norm(_all_text())
    assert "visible" in text


def test_production_executed_true_count_recorded() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text


def test_no_production_or_external_action_claimed() -> None:
    text = _norm(_all_text())
    assert "no production action" in text or "production action: no" in text
    assert "no external action" in text or "external action: no" in text
    assert "workflow dispatch" in text


def test_fe1b_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1b", "fe.1c", "fe.1d"):
        assert phrase in text, phrase
    assert "unauthorized" in text or "not authorized" in text


def test_no_merge_performed_or_authorized() -> None:
    text = _norm(_all_text())
    assert "does not merge" in text or "not merged" in text
    assert "merge authorization" in text


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in REVIEW_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    text = _all_text().lower()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_marker_pass_present() -> None:
    text = REVIEW_DOCS["fe1a-product-owner-validation"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1A_PRODUCT_OWNER_VALIDATION_VERIFY: PASS" in text
