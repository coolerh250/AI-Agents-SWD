"""Step 62 -- production readiness runtime report generator (offline, safe)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".runtime" / "readiness" / "production-readiness-gate-report.json"


def test_generator_produces_safe_report() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_production_readiness_gate_report.py")],
        check=True,
        cwd=ROOT,
    )
    d = json.loads(REPORT.read_text(encoding="utf-8"))
    assert d["production_ready"] is False
    assert d["production_approval"] is False
    assert d["production_action_allowed"] is False
    assert int(d["production_executed_true_count"]) == 0
    assert d["decision"]["decision"] in (
        "not_ready",
        "blocked_by_missing_evidence",
        "blocked_by_policy",
        "blocked_by_production_prerequisites",
        "ready_for_operator_review",
        "operator_review_requested",
    )
    assert d["decision"]["production_ready"] is False


def test_report_has_no_secret_shape() -> None:
    raw = REPORT.read_text(encoding="utf-8")
    for shape in ("ghp_", "-----BEGIN", "AKIA"):
        assert shape not in raw
