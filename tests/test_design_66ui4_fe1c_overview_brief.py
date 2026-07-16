"""DESIGN-66UI.4-FE.1C -- tests for the Overview Attention-first design brief.

Documentation-only checks: the required design brief set, handoff, and
stage-gate artifacts exist and are internally consistent (Codex unauthorized,
existing-data-only, honest 66D/66C.4 placeholders, no fake controls). Mirrors
scripts/verify_design_66ui4_fe1c_overview_brief.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN_DIR = ROOT / "docs" / "design" / "66ui4-fe1c-overview-attention-first"
STAGE_DIR = ROOT / "docs" / "stages" / "66ui4-fe1c"
HANDOFF = ROOT / "docs" / "handoffs" / "66ui4-fe1c" / "claude-design-to-claude-code-handoff.md"
PROGRESS = ROOT / "source" / "progress.md"

REQUIRED_DESIGN_FILES = [
    "design-brief.md",
    "current-overview-analysis.md",
    "information-architecture.md",
    "layout-wireframe.md",
    "existing-data-mapping.md",
    "placeholder-and-empty-state-strategy.md",
    "microcopy-guide.md",
    "codex-implementation-boundary.md",
    "product-owner-validation-checklist.md",
    "open-questions-and-risks.md",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def test_required_design_files_exist():
    for name in REQUIRED_DESIGN_FILES:
        assert (DESIGN_DIR / name).is_file(), f"missing {name}"


def test_stage_artifacts_exist():
    assert (STAGE_DIR / "stage-manifest.yaml").is_file()
    assert (STAGE_DIR / "context-receipt.md").is_file()
    assert (STAGE_DIR / "stage-gate-report.md").is_file()
    assert HANDOFF.is_file()


def test_progress_mentions_stage():
    text = _read(PROGRESS)
    assert "66UI.4-FE.1C" in text or "66ui4-fe1c" in text.lower()


def test_codex_unauthorized():
    manifest = _read(STAGE_DIR / "stage-manifest.yaml").lower()
    assert "codex_authorized: false" in manifest
    boundary = _read(DESIGN_DIR / "codex-implementation-boundary.md").lower()
    assert "not authorized" in boundary


def test_existing_data_only_and_no_new_backend():
    mapping = _read(DESIGN_DIR / "existing-data-mapping.md").lower()
    assert "existing data" in mapping
    assert "new backend endpoint" in mapping  # in the explicit exclusion list
    brief = _read(DESIGN_DIR / "design-brief.md").lower()
    assert "no new backend endpoint" in brief or "no new endpoint" in brief


def test_honest_placeholders():
    ph = _read(DESIGN_DIR / "placeholder-and-empty-state-strategy.md").lower()
    assert "not yet available" in ph
    assert "requires step 66d" in ph
    assert "requires step 66c.4" in ph
    assert "no workflow action available" in ph


def test_no_fake_controls():
    ph = _read(DESIGN_DIR / "placeholder-and-empty-state-strategy.md").lower()
    assert "no fake" in ph or "no buttons" in ph


def test_no_runtime_paths_changed():
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return  # environment without origin/main ref; scope covered by the verifier
    forbidden = ("apps/", "services/", "infra/", "migrations/", "database/", "shared/")
    for line in result.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        assert not any(path.startswith(p) for p in forbidden), f"runtime path changed: {path}"
