"""Step 54.2 -- local SAST runner detects unsafe fixture patterns."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "sast_unsafe_samples.py"


def _runner():
    spec = importlib.util.spec_from_file_location(
        "_sast_runner", ROOT / "scripts" / "run_local_sast_scan.py"
    )
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_detects_unsafe_fixture_patterns() -> None:
    runner = _runner()
    rules = {
        f.rule_id
        for f in runner.scan_text(FIXTURE.read_text(encoding="utf-8"), "tests/fixtures/x.py")
    }
    assert {"PY-EVAL", "PY-EXEC", "PY-SHELL-TRUE", "PY-YAML-LOAD", "PY-TLS-VERIFY-OFF"} <= rules


def test_codebase_scan_runs_and_records_limitations() -> None:
    result = _runner().run()
    assert result.scan_type == "sast"
    assert result.status in ("passed", "completed_with_findings")
    assert result.limitations  # limited custom baseline disclosed
    assert result.production_ready is False
    assert result.network_used is False
    assert result.source_uploaded is False
