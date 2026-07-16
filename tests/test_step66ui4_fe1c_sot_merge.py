"""Step 66UI.4-FE.1C-SOT-M -- FE.1C design/review source-of-truth merge (docs-only checks).

This file changes no runtime code. It confirms the source-of-truth merge record and test record
exist and state the required facts: PR #8/design/review commits, the FE.1C review PASS marker, the
existing-data-only principle, the /tasks status-filter usage decision, the FE.1B.1 safety reuse
dependency now satisfied, the agent-execution status mapping, that 66D/66C.4/notifications/pipeline
items remain placeholder-only, no fake counts/controls, Codex FE.1C remaining unauthorized, FE.1D
remaining unauthorized, no frontend runtime/backend/API/database/workflow change, no production/
external action, and Local Artifact Reconciliation recorded.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-sot-merge-record": ROOT
    / "docs"
    / "design"
    / "66ui4-fe1c-overview-attention-first"
    / "source-of-truth-merge-record.md",
    "fe1c-sot-merge-test-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-source-of-truth-merge-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

DESIGN_COMMIT = "0c7762e"
REVIEW_COMMIT = "4eb1279"

FE1C_ARTIFACTS = [
    ROOT / "docs" / "design" / "66ui4-fe1c-overview-attention-first" / "design-brief.md",
    ROOT
    / "docs"
    / "design"
    / "66ui4-fe1c-overview-attention-first"
    / "claude-code-architecture-review.md",
    ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1c-overview-attention-first"
    / "frontend-implementation-boundary.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "codex-readiness-boundary.md",
    ROOT / "docs" / "handoffs" / "66ui4-fe1c" / "claude-design-to-claude-code-handoff.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c-design-review-record.md",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_fe1c_artifacts_consolidated_on_main() -> None:
    for p in FE1C_ARTIFACTS:
        assert p.is_file(), p


def test_pr8_design_review_commits_referenced() -> None:
    text = _norm(_all_text())
    assert "pr #8" in text
    assert DESIGN_COMMIT in text
    assert REVIEW_COMMIT in text


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c-sot-m" in text


def test_fe1c_review_pass_marker_referenced() -> None:
    text = _norm(_all_text())
    assert "step66ui4_fe1c_design_review_verify: pass" in text


def test_existing_data_only_recorded() -> None:
    text = _norm(_all_text())
    assert "existing-data-only" in text or "existing data only" in text


def test_tasks_status_filter_usage_recorded() -> None:
    text = _norm(_all_text())
    assert "status filter" in text or "status=clarification_needed" in text


def test_fe1b1_safety_reuse_satisfied() -> None:
    text = _norm(_all_text())
    assert "satisfied" in text or "unblocked" in text


def test_agent_execution_status_mapping_recorded() -> None:
    text = _norm(_all_text())
    assert "completed" in text
    assert "needs review" in text
    assert "not reported" in text


def test_placeholder_only_items_recorded() -> None:
    text = _norm(_all_text())
    for phrase in ("66d", "66c.4", "placeholder"):
        assert phrase in text, phrase


def test_no_fake_counts_or_controls() -> None:
    text = _norm(_all_text())
    assert "no fake counts" in text
    assert "no fake controls" in text


def test_codex_fe1c_and_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "codex fe.1c" in text
    assert "fe.1d" in text
    assert "not authorized" in text or "unauthorized" in text


def test_no_frontend_runtime_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("frontend runtime", "backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text), term


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


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


def test_marker_pass_present() -> None:
    text = DOCS["fe1c-sot-merge-test-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C_SOT_MERGE_VERIFY: PASS" in text
