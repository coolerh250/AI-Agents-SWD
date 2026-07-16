"""Step 66UI.4-FE.1B.1-P -- Safety Field Mapping Calibration planning (docs-only checks).

This file changes no runtime code. It confirms the mapping plan, frontend
implementation boundary, planning record, and stage artifacts exist and
state the required facts: Codex/FE.1C/FE.1D remaining unauthorized, no
backend/API/database/workflow change, the /operations/safety response
shape being unchanged, a frontend-only future calibration, raw evidence
preservation, the conservative fallback, the accepted Unavailable gap
reference, and that no runtime files were changed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-safety-field-mapping-plan": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-safety-field-mapping-plan.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1b1-safety-field-mapping"
    / "frontend-implementation-boundary.md",
    "planning-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b1-safety-field-mapping-planning-record.md",
    "stage-manifest": ROOT / "docs" / "stages" / "66ui4-fe1b1" / "stage-manifest.yaml",
    "context-receipt": ROOT / "docs" / "stages" / "66ui4-fe1b1" / "context-receipt.md",
    "stage-gate-report": ROOT / "docs" / "stages" / "66ui4-fe1b1" / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values())


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_progress_references_stage() -> None:
    text = _norm(PROGRESS.read_text(encoding="utf-8"))
    assert "66ui.4-fe.1b.1-p" in text


def test_marker_verbatim() -> None:
    assert "STEP66UI4_FE1B1_PLANNING_VERIFY" in _all_text()


def test_codex_and_fe1c_fe1d_unauthorized() -> None:
    text = _norm(_all_text())
    assert "codex" in text
    assert "unauthorized" in text or "not authorized" in text
    for phrase in ("fe.1c", "fe.1d"):
        assert phrase in text, phrase


def test_no_backend_api_database_workflow_change() -> None:
    text = _norm(_all_text())
    for term in ("backend", "api", "database", "workflow"):
        assert re.search(rf"no [\w/]*{term}", text), term


def test_response_shape_unchanged() -> None:
    text = _norm(_all_text())
    assert "response shape" in text
    assert "unchanged" in text


def test_frontend_only_future_calibration() -> None:
    text = _norm(_all_text())
    assert "frontend-only" in text or "frontend only" in text


def test_raw_evidence_preservation() -> None:
    text = _norm(_all_text())
    assert "raw evidence" in text
    assert "accessible" in text


def test_conservative_fallback_recorded() -> None:
    text = _norm(_all_text())
    assert "conservative" in text


def test_accepted_gap_referenced() -> None:
    text = _norm(_all_text())
    assert "unavailable" in text
    assert "dispatch_enabled" in text
    assert "approval_required" in text


def test_no_runtime_files_changed() -> None:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    cached = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    changed = {
        line.strip().replace("\\", "/")
        for line in (result.stdout.splitlines() + cached.stdout.splitlines())
        if line.strip()
    }
    forbidden_prefixes = ("apps/", "services/", "infra/", "migrations/", "database/")
    forbidden = [p for p in changed if any(p.startswith(prefix) for prefix in forbidden_prefixes)]
    assert not forbidden, forbidden


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
    text = DOCS["planning-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_FE1B1_PLANNING_VERIFY: PASS" in text
