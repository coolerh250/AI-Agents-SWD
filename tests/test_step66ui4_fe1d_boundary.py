"""Step 66UI.4-FE.1D-BOUNDARY -- Codex implementation boundary consolidation (docs-only checks).

This file changes no runtime code. It confirms the boundary, PO decision record, slicing plan,
consolidation record, and stage artifacts exist and state the required facts: Codex remains
unauthorized, "+ Create task" keep decision, delivery_package_ready_for_admin_console rename
deferred to 66D, SPA deep-link fallback and two-way URL sync excluded, no backend/API/database/
workflow/new-endpoint change, no runtime source files changed, Slice 1 and Slice 2 recorded, and
Product Owner validation required.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONTRACT_DOCS = {
    "codex-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1d-navigation-microcopy"
    / "codex-implementation-boundary.md",
    "po-decision-record": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1d-navigation-microcopy"
    / "po-decision-record.md",
    "implementation-slicing-plan": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1d-navigation-microcopy"
    / "implementation-slicing-plan.md",
}

RECORD_DOC = ROOT / "docs" / "test" / "step66ui4-fe1d-boundary-consolidation-record.md"

STAGE_DOCS = {
    "stage-manifest": ROOT / "docs" / "stages" / "66ui4-fe1d-boundary" / "stage-manifest.yaml",
    "context-receipt": ROOT / "docs" / "stages" / "66ui4-fe1d-boundary" / "context-receipt.md",
    "stage-gate-report": ROOT / "docs" / "stages" / "66ui4-fe1d-boundary" / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

ALL_TEXT_DOCS = {**CONTRACT_DOCS, "boundary-consolidation-record": RECORD_DOC}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in ALL_TEXT_DOCS.values())


def test_contract_docs_exist() -> None:
    for name, p in CONTRACT_DOCS.items():
        assert p.is_file(), name


def test_record_doc_exists() -> None:
    assert RECORD_DOC.is_file()


def test_stage_docs_exist() -> None:
    for name, p in STAGE_DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1d-boundary" in text


def test_codex_unauthorized() -> None:
    text = _norm(_all_text())
    assert "codex" in text
    assert "codex remains unauthorized" in text or "not authorized" in text


def test_create_task_kept_unchanged() -> None:
    text = _norm(_all_text())
    assert "create task" in text
    assert "unchanged" in text


def test_delivery_package_rename_deferred_to_66d() -> None:
    text = _norm(_all_text())
    assert "delivery_package_ready_for_admin_console" in text
    assert "66d" in text
    assert "defer" in text


def test_spa_deep_link_and_two_way_sync_excluded() -> None:
    text = _norm(_all_text())
    assert "spa deep-link" in text
    assert "two-way url sync" in text


def test_no_backend_api_database_workflow_new_endpoint_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text) or f"{term} change" in text, term
    assert re.search(r"no [\w/]*new endpoint", text) or "new endpoint" in text


def test_no_runtime_source_files_changed_statement() -> None:
    text = _norm(_all_text())
    assert "no runtime" in text or "runtime source files changed" in text


def test_slice_1_and_slice_2_recorded() -> None:
    text = _norm(_all_text())
    assert "slice 1" in text
    assert "slice 2" in text


def test_product_owner_validation_required_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner validation" in text


def test_product_owner_authorization_recorded() -> None:
    text = _all_text()
    assert "授權" in text


def test_no_local_windows_paths_committed() -> None:
    windows_path_shape = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)
    for name, p in ALL_TEXT_DOCS.items():
        assert not windows_path_shape.search(p.read_text(encoding="utf-8")), name


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in ALL_TEXT_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    text = _all_text().lower()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_marker_pass_present() -> None:
    text = RECORD_DOC.read_text(encoding="utf-8")
    assert "STEP66UI4_FE1D_BOUNDARY_VERIFY: PASS" in text
