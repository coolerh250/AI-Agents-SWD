"""Step 66UI.4-FE.1A-R -- Visual polish review (docs-only checks).

Review stage: this file itself changes no runtime code. It confirms the
Claude Code FE.1A review doc and review record exist and state the
required facts: PR #6/branch/commit references, the FE.1A marker,
FE.1B/FE.1C/FE.1D remaining unauthorized, and no forbidden scope/action
claims.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "fe1a-claude-code-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1a-claude-code-review.md",
    "fe1a-review-record": ROOT / "docs" / "test" / "step66ui4-fe1a-review-record.md",
}

PROGRESS_MD = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1A_REVIEW_VERIFY: PASS"


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


def test_marker_present() -> None:
    assert MARKER in _all_text()


def test_fe1b_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1b", "fe.1c", "fe.1d"):
        assert phrase in text, phrase
    assert "unauthorized" in text


def test_no_backend_api_database_workflow_infra_change_claimed() -> None:
    text = _norm(_all_text())
    assert "no backend" in text or "backend changed: no" in text
    assert "no api" in text or "api changed: no" in text
    assert "no database" in text or "database changed: no" in text
    assert "workflow" in text
    assert "infra" in text


def test_no_production_or_external_action_claimed() -> None:
    text = _norm(_all_text())
    assert "no production action" in text
    assert "external action" in text


def test_no_delivery_reminder_pipeline_dragdrop_claimed() -> None:
    text = _norm(_all_text())
    assert "delivery real ui" in text
    assert "reminder" in text
    assert "pipeline" in text
    assert "drag-and-drop" in text or "drag/drop" in text


def test_local_only_and_unrelated_files_excluded() -> None:
    text = _norm(_all_text())
    assert ".tools" in text
    assert "platform-progress-admin-console-proposal" in text


def test_review_verdict_stated() -> None:
    combined = _all_text()
    assert any(v in combined for v in ("PASS", "PASS_WITH_GAPS", "FAIL"))


def test_progress_md_updated() -> None:
    text = _norm(PROGRESS_MD.read_text(encoding="utf-8"))
    assert "66ui4-fe1a-r" in text.replace(".", "-")
    assert "pr #6" in text or "frontend/66ui4-fe1a-visual-polish" in text


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
