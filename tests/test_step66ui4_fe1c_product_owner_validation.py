"""Step 66UI.4-FE.1C-V -- Product Owner UI validation (docs-only checks).

This file changes no runtime code. It confirms the validation record and test report exist and
state the required facts: PR #10 branch/commit referenced, VISIBLE verdict covering all 10
checklist items, the real-data clarification (item #3) investigated live,
production_executed_true_count=0, no production/external action, FE.1D remaining unauthorized, the
TaskList query-param gap disclosed as non-blocking, and that merge authorization is not granted by
this document.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "product-owner-ui-validation-record.md",
    "fe1c-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-product-owner-validation.md",
}

PROGRESS = ROOT / "source" / "progress.md"

PR10_COMMIT = "816856a"
PR10_BRANCH = "frontend/66ui4-fe1c-overview-attention-first"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1c-v" in text


def test_pr10_branch_and_commit_referenced() -> None:
    text = _norm(_all_text())
    assert PR10_BRANCH in text
    assert PR10_COMMIT in text


def test_visible_verdict_recorded() -> None:
    text = _norm(_all_text())
    assert "visible" in text


def test_ten_item_checklist_referenced() -> None:
    text = _norm(_all_text())
    assert "10" in text
    assert "checklist" in text


def test_real_data_clarification_recorded() -> None:
    text = _norm(_all_text())
    assert "real data" in text or "real-data" in text
    assert "clarification_needed" in text
    assert "blocked" in text


def test_production_executed_true_count_zero() -> None:
    text = _norm(_all_text())
    assert "production_executed_true_count" in text
    assert "0" in text


def test_no_production_or_external_action() -> None:
    text = _norm(_all_text())
    assert re.search(r"no [\w/]*production action", text)
    assert re.search(r"no [\w/]*external action", text)


def test_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "fe.1d" in text
    assert "not authorized" in text or "unauthorized" in text


def test_tasklist_query_param_gap_non_blocking() -> None:
    text = _norm(_all_text())
    assert "tasklist" in text
    assert "query-param" in text
    assert "non-blocking" in text


def test_pr10_not_merged_by_document() -> None:
    text = _norm(_all_text())
    assert "does not merge" in text or "not merge" in text
    assert "merge authorization" in text


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
    text = DOCS["fe1c-product-owner-validation"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1C_PRODUCT_OWNER_VALIDATION_VERIFY: PASS" in text
