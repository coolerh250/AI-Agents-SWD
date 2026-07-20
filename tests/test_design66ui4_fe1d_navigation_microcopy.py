"""Step 66UI.4-FE.1D-DESIGN -- tests for the Navigation Polish + Microcopy design.

Documentation-only checks mirroring
scripts/verify_design66ui4_fe1d_navigation_microcopy.py: the required design
brief set and stage-gate artifacts exist and are internally consistent (Codex
unauthorized, no backend/endpoint/implementation claims, SPA deep-link
fallback explicitly out of scope, no runtime files changed).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN_DIR = ROOT / "docs" / "design" / "66ui4-fe1d-navigation-microcopy"
STAGE_DIR = ROOT / "docs" / "stages" / "66ui4-fe1d-navigation-microcopy-design"
PROGRESS = ROOT / "source" / "progress.md"

REQUIRED_DESIGN_FILES = [
    "design-brief.md",
    "navigation-polish-spec.md",
    "microcopy-guide.md",
    "field-label-cleanup-map.md",
    "engineering-field-exposure-reduction.md",
    "platform-ops-density-spec.md",
    "product-owner-review-checklist.md",
    "codex-implementation-notes.md",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _all_design_text() -> str:
    return " ".join(_read(DESIGN_DIR / n).lower() for n in REQUIRED_DESIGN_FILES)


def test_required_design_files_exist():
    for name in REQUIRED_DESIGN_FILES:
        assert (DESIGN_DIR / name).is_file(), f"missing {name}"


def test_stage_artifacts_exist():
    assert (STAGE_DIR / "stage-manifest.yaml").is_file()
    assert (STAGE_DIR / "context-receipt.md").is_file()
    assert (STAGE_DIR / "stage-gate-report.md").is_file()


def test_progress_mentions_stage():
    text = _read(PROGRESS)
    assert "FE.1D-DESIGN" in text or "66ui4-fe1d" in text.lower()


def test_codex_unauthorized():
    manifest = _read(STAGE_DIR / "stage-manifest.yaml").lower()
    assert "codex_authorized: false" in manifest
    notes = _read(DESIGN_DIR / "codex-implementation-notes.md").lower()
    assert "not authorized" in notes


def test_no_backend_or_new_endpoint_claimed():
    brief = _read(DESIGN_DIR / "design-brief.md").lower()
    assert "no backend" in brief
    assert "no new endpoint" in brief


def test_deep_link_out_of_scope():
    text = _all_design_text()
    assert "deep-link" in text or "deep link" in text
    assert any(
        cue in text
        for cue in ("out of fe.1d scope", "out of scope", "backend change", "not fe.1d")
    )


def test_no_runtime_paths_changed():
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return
    forbidden = ("apps/", "services/", "infra/", "migrations/", "database/", "shared/")
    for line in result.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        assert not any(path.startswith(p) for p in forbidden), f"runtime path changed: {path}"
