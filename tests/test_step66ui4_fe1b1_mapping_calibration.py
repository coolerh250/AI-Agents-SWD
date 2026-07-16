from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_step66ui4_fe1b1_mapping_calibration_verifier_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/verify_step66ui4_fe1b1_mapping_calibration.py"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STEP66UI4_FE1B1_MAPPING_CALIBRATION_VERIFY: PASS" in result.stdout
