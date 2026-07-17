"""Step 66UI.4-FE.1C-LV -- restore test runtime + live agent-execution verification (docs-only).

This file changes no runtime code. It confirms the live verification record and status
verification doc exist and state the required facts: Product Owner authorization, the runtime
stopped-state baseline, the restoration action taken, /operations/agent-executions availability and
observed status values, mapping compatibility, PR #10 review gap #1 closure, PR #10 not merged/not
deployed, no frontend/backend/API/database/workflow change, no production/external action, FE.1D
remaining unauthorized, and Local Artifact Reconciliation recorded.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-live-verification-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-live-agent-execution-verification-record.md",
    "fe1c-live-status-verification": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "live-agent-execution-status-verification.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR10_COMMIT = "816856a"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c-lv" in text


def test_product_owner_authorization_recorded() -> None:
    text = _all_text()
    assert "授權" in text
    assert "Product Owner authorization" in text


def test_runtime_stopped_baseline_recorded() -> None:
    text = _norm(_all_text())
    assert "stopped" in text
    assert "exited" in text or "27 application containers" in text


def test_restoration_action_recorded() -> None:
    text = _norm(_all_text())
    assert "restoration" in text or "restored" in text
    assert "no rebuild" in text
    assert "no config" in text or "no compose/env file change" in text


def test_pr10_commit_referenced() -> None:
    text = _norm(_all_text())
    assert PR10_COMMIT in text


def test_agent_executions_availability_recorded() -> None:
    text = _norm(_all_text())
    assert "agent-executions" in text
    assert "reachable" in text


def test_observed_status_values_recorded() -> None:
    text = _norm(_all_text())
    assert "completed" in text
    assert "20" in text


def test_mapping_compatibility_recorded() -> None:
    text = _norm(_all_text())
    assert "mapping compatibility" in text or "maps correctly" in text


def test_gap_one_cleared() -> None:
    text = _norm(_all_text())
    assert "gap #1" in text or "gap 1" in text
    assert "cleared" in text


def test_pr10_not_merged_not_deployed() -> None:
    text = _norm(_all_text())
    assert "pr #10 merged: no" in text
    assert "pr #10 deployed: no" in text


def test_no_frontend_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("frontend code", "backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text), term


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


def test_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d" in text
    assert "not authorized" in text or "unauthorized" in text


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
    text = DOCS["fe1c-live-verification-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C_LIVE_VERIFICATION_VERIFY: PASS" in text
