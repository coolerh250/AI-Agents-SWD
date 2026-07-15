"""Step 66UI.4-FE.1B-R -- Calm Safety Posture review (docs-only checks).

This file changes no runtime code. It confirms the review doc and review
record exist and state the required facts: PR #7/branch/commit, the FE.1B
review marker, FE.1C/FE.1D remaining unauthorized, existing /operations/
safety data only, raw safety evidence remaining accessible, no backend/API/
database/workflow/infra change, no new safety endpoint/computation, no
production/external action, no Delivery/Reminder/Pipeline content, the
excluded local-only paths being absent, and a stated review result.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "fe1b-claude-code-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b-claude-code-review.md",
    "fe1b-review-record": ROOT / "docs" / "test" / "step66ui4-fe1b-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


def test_pr_branch_commit_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #7" in text
    assert "frontend/66ui4-fe1b-calm-safety" in text
    assert "6cf8efe" in text


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1b-r" in text


def test_marker_verbatim() -> None:
    assert "STEP66UI4_FE1B_REVIEW_VERIFY" in _all_text()


def test_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1c", "fe.1d"):
        assert phrase in text, phrase
    assert "unauthorized" in text or "not authorized" in text


def test_existing_safety_data_and_raw_evidence() -> None:
    text = _norm(_all_text())
    assert "/operations/safety" in text
    assert "raw" in text and "evidence" in text
    assert "accessible" in text


def test_no_backend_api_database_workflow_infra_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow", "infra"):
        assert re.search(rf"no [\w/]*{term}", text), term


def test_no_new_safety_endpoint_or_computation() -> None:
    text = _norm(_all_text())
    assert "no new safety endpoint" in text
    assert "no new backend safety computation" in text


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


def test_no_delivery_reminder_pipeline_content() -> None:
    text = _norm(_all_text())
    assert "no delivery" in text
    assert "no reminder" in text
    assert "no pipeline" in text or "pipeline board" in text


def test_excluded_local_only_paths_absent() -> None:
    text = _norm(_all_text())
    assert ".tools/" in text
    assert "docs/product/platform-progress-admin-console-proposal.md" in text


def test_review_result_stated() -> None:
    text = _norm(_all_text())
    assert any(v in text for v in ("pass_with_gaps", "**pass.**", "verdict: **pass", "pass."))


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
    text = REVIEW_DOCS["fe1b-review-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1B_REVIEW_VERIFY: PASS" in text
