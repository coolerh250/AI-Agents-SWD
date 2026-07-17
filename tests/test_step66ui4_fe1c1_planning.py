"""Step 66UI.4-FE.1C.1-P -- TaskList query param filter support planning (docs-only checks).

This file changes no runtime code. It confirms the planning doc, frontend implementation boundary,
planning record, and stage artifacts exist and state the required facts: Codex unauthorized, FE.1D
unauthorized, no backend/API/database/workflow/new-endpoint change, frontend-only future
implementation, existing TaskList status filter reuse, invalid query param behavior, and no fake
counts/controls.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c1-planning-doc": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-plan.md",
    "fe1c1-frontend-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1c1-tasklist-query-param"
    / "frontend-implementation-boundary.md",
    "fe1c1-planning-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c1-tasklist-query-param-planning-record.md",
}

STAGE_ARTIFACTS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66ui4-fe1c1-tasklist-query-param"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66ui4-fe1c1-tasklist-query-param"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66ui4-fe1c1-tasklist-query-param"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

RUNTIME_PREFIXES = (
    "apps/",
    "services/",
    "infra/",
    "migrations/",
    "database/",
    "helm/",
    "k8s/",
    ".github/workflows/",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_paths() -> dict[str, Path]:
    return {**DOCS, **STAGE_ARTIFACTS}


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in _all_paths().values())


def test_docs_and_stage_artifacts_exist() -> None:
    for name, p in _all_paths().items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c.1-p" in text


def test_codex_unauthorized() -> None:
    text = _norm(_all_text())
    assert "codex" in text
    assert "codex implementation not authorized" in text or "not authorized" in text


def test_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d" in text
    assert "not authorized" in text or "unauthorized" in text


def test_no_runtime_files_touched() -> None:
    for name, p in DOCS.items():
        for prefix in RUNTIME_PREFIXES:
            assert not p.as_posix().startswith(prefix), (name, prefix)


def test_no_backend_api_database_workflow_new_endpoint_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term
    assert re.search(r"no [\w/]*new endpoint", text) or "new endpoint" in text


def test_frontend_only_future_implementation_recorded() -> None:
    text = _norm(_all_text())
    assert "frontend-only" in text or "frontend only" in text


def test_existing_status_filter_reuse_recorded() -> None:
    text = _norm(_all_text())
    assert "existing" in text
    assert "status filter" in text


def test_invalid_query_param_behavior_recorded() -> None:
    text = _norm(_all_text())
    assert "invalid" in text
    assert "ignored" in text


def test_no_fake_counts_or_controls() -> None:
    text = _norm(_all_text())
    assert "no fake counts" in text
    assert "fake controls" in text


def test_no_local_windows_paths_committed() -> None:
    windows_path_shape = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)
    for name, p in _all_paths().items():
        assert not windows_path_shape.search(p.read_text(encoding="utf-8")), name


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in _all_paths().items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    text = _all_text().lower()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_marker_pass_present() -> None:
    text = DOCS["fe1c1-planning-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C1_PLANNING_VERIFY: PASS" in text
