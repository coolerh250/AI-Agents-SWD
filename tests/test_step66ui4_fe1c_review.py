"""Step 66UI.4-FE.1C-R -- Claude Code review of PR #10 (docs-only checks).

This file changes no runtime code. It confirms the review doc and review record exist and state
the required facts: PR #10/branch/commit, the Codex FE.1C implementation marker, a recorded review
result, the live agent-execution verification result, the current-work 5/updated_at-desc review,
the existing-data-only review, no backend/API/database/workflow change, no new endpoint, no fake
counts/controls, FE.1D remaining unauthorized, Local Artifact Reconciliation recorded, and no local
Windows path exposure.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-claude-code-implementation-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "claude-code-implementation-review.md",
    "fe1c-implementation-review-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-implementation-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR10_COMMIT = "816856a9ffe2b7a14aa0a1a070d9538f2231cf67"
PR10_BRANCH = "frontend/66ui4-fe1c-overview-attention-first"
IMPLEMENTATION_MARKER = "STEP66UI4_FE1C_IMPLEMENTATION_VERIFY"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_pr10_branch_commit_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #10" in text
    assert PR10_BRANCH in text
    assert PR10_COMMIT.lower() in text


def test_implementation_marker_referenced() -> None:
    assert IMPLEMENTATION_MARKER in _all_text()


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c-r" in text


def test_review_result_recorded() -> None:
    text = _norm(_all_text())
    assert re.search(r"\bpass_with_gaps\b|\bpass\b|\bfail\b", text)


def test_live_agent_execution_verification_recorded() -> None:
    text = _norm(_all_text())
    assert "agent-execution" in text or "agent execution" in text
    assert "live" in text


def test_current_work_five_updated_at_desc_reviewed() -> None:
    text = _norm(_all_text())
    assert "updated_at" in text
    assert " 5 " in text or "five" in text or "5 tasks" in text


def test_existing_data_only_reviewed() -> None:
    text = _norm(_all_text())
    assert "existing-data-only" in text or "existing data only" in text


def test_no_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text), term


def test_no_new_endpoint() -> None:
    text = _norm(_all_text())
    assert "no new endpoint" in text


def test_no_fake_counts_or_controls_reviewed() -> None:
    text = _norm(_all_text())
    assert "no fake count" in text or "fake counts" in text
    assert "fake control" in text


def test_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d" in text
    assert "unauthorized" in text or "not authorized" in text


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


def test_marker_recorded() -> None:
    text = DOCS["fe1c-claude-code-implementation-review"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C_REVIEW_VERIFY: PASS_WITH_GAPS" in text
