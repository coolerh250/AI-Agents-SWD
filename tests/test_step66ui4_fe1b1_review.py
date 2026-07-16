"""Step 66UI.4-FE.1B.1-R -- Claude Code review of PR #9 (docs-only checks).

This file changes no runtime code. It confirms the review doc and review record exist and state
the required facts: PR #9/branch/commit, the FE.1B.1 implementation marker, FE.1C/FE.1D remaining
unauthorized, frontend-only mapping calibration, no backend/API/database/workflow/infra change, no
/operations/safety response shape change, no production/external action, raw evidence accessible,
conservative fallback preserved, retired-field behavior reviewed, source-of-truth planning-branch
risk reviewed, no local Windows paths committed, and a recorded PASS/PASS_WITH_GAPS/FAIL result.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-claude-code-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-claude-code-review.md",
    "fe1b1-review-record": ROOT / "docs" / "test" / "step66ui4-fe1b1-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR9_COMMIT = "974822d940c0e1ed9d061fbfe68fbed40ebd1fc0"
PR9_BRANCH = "frontend/66ui4-fe1b1-safety-field-mapping"
IMPLEMENTATION_MARKER = "STEP66UI4_FE1B1_MAPPING_CALIBRATION_VERIFY"


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
    assert PR9_COMMIT.lower() in text


def test_implementation_marker_referenced() -> None:
    assert IMPLEMENTATION_MARKER in _all_text()


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1b.1-r" in text


def test_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    for phrase in ("fe.1c", "fe.1d"):
        assert phrase in text, phrase
    assert "unauthorized" in text or "not authorized" in text


def test_frontend_only_mapping_calibration_documented() -> None:
    text = _norm(_all_text())
    assert "frontend-only" in text or "frontend only" in text
    assert "mapping calibration" in text


def test_no_backend_api_database_workflow_infra_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow", "infra"):
        assert re.search(rf"no [\w/]*{term}", text), term


def test_response_shape_unchanged() -> None:
    text = _norm(_all_text())
    assert "/operations/safety" in text
    assert "response shape" in text


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


def test_raw_evidence_accessible() -> None:
    text = _norm(_all_text())
    assert "evidence" in text
    assert "accessible" in text


def test_conservative_fallback_preserved() -> None:
    text = _norm(_all_text())
    assert "conservative" in text


def test_retired_field_behavior_reviewed() -> None:
    text = _norm(_all_text())
    for field in (
        "dispatch_enabled",
        "resume_dispatch_enabled",
        "approval_required",
        "requires_approval",
    ):
        assert field in text, field
    assert "not applicable at this endpoint" in text


def test_source_of_truth_planning_branch_risk_reviewed() -> None:
    text = _norm(_all_text())
    assert "source-of-truth" in text
    assert "review/66ui4-fe1b1-safety-field-mapping-plan" in text
    assert "option c" in text or "option a" in text or "option b" in text


def test_no_local_windows_paths_committed() -> None:
    windows_path_shape = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)
    for name, p in DOCS.items():
        assert not windows_path_shape.search(p.read_text(encoding="utf-8")), name


def test_review_result_recorded() -> None:
    text = _norm(_all_text())
    assert re.search(r"\bpass\b|\bpass_with_gaps\b|\bfail\b", text)


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
    text = DOCS["fe1b1-review-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1B1_REVIEW_VERIFY: PASS" in text
