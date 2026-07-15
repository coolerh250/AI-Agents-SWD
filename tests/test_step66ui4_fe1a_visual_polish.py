"""Step 66UI.4-FE.1A visual polish verifier test."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66UI4_FE1A_VISUAL_POLISH_VERIFY: PASS"


def test_step66ui4_fe1a_visual_polish_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_step66ui4_fe1a_visual_polish.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert MARKER in result.stdout
