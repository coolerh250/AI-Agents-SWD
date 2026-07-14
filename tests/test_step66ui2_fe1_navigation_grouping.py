"""Step 66UI.2-FE.1 -- Navigation Grouping / IA Shell verifier test."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66UI2_FE1_NAVIGATION_GROUPING_VERIFY: PASS"


def test_step66ui2_fe1_navigation_grouping_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_step66ui2_fe1_navigation_grouping.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert MARKER in result.stdout
