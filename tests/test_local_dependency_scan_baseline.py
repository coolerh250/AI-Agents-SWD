"""Step 54.2 -- local dependency scan runner (manifest policy, no CVE lookup)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location(
        "_dep_runner", ROOT / "scripts" / "run_local_dependency_scan.py"
    )
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_runs_and_records_python_lockfile_gap() -> None:
    result = _runner().run()
    assert result.scan_type == "dependency"
    assert result.status in ("passed", "completed_with_findings")
    lims = " ".join(result.limitations)
    assert "python_lockfile_missing" in lims


def test_no_cve_lookup_and_node_lockfile_recorded() -> None:
    result = _runner().run()
    lims = " ".join(result.limitations)
    assert "no_cve_lookup" in lims
    assert "node_lockfile" in lims
    assert result.network_used is False
    assert result.production_ready is False
