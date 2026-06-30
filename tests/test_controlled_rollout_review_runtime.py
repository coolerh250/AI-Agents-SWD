"""Step 63A -- controlled rollout review report generator (offline, safe)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".runtime" / "readiness" / "controlled-rollout-go-no-go-review.json"


def test_generator_produces_safe_review() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_controlled_rollout_go_no_go_review.py")],
        check=True,
        cwd=ROOT,
    )
    d = json.loads(REPORT.read_text(encoding="utf-8"))
    assert d["production_ready"] is False
    assert d["production_approval"] is False
    assert d["production_action_allowed"] is False
    assert int(d["production_executed_true_count"]) == 0
    assert d["recommendation"]["recommendation"] in ("go", "conditional_go", "no_go")
    assert d["recommendation"]["recommendation_is_approval"] is False


def test_report_has_no_secret_shape() -> None:
    raw = REPORT.read_text(encoding="utf-8")
    for shape in ("ghp_", "-----BEGIN", "AKIA"):
        assert shape not in raw
