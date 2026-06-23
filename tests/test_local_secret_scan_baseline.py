"""Step 54.2 -- local secret scan runner produces a clean, redacted baseline."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}|BEGIN [A-Z ]*PRIVATE KEY)"
)


def _runner():
    spec = importlib.util.spec_from_file_location(
        "_secret_runner", ROOT / "scripts" / "run_local_secret_scan.py"
    )
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_runs_and_reports_no_confirmed_secret() -> None:
    result = _runner().run()
    assert result.scan_type == "secret"
    assert result.status in ("passed", "completed_with_findings")
    # no real secrets are committed -> zero confirmed (critical/high)
    assert result.findings_summary.critical == 0
    assert result.findings_summary.high == 0
    assert result.production_ready is False


def test_report_has_no_raw_credential() -> None:
    result = _runner().run()
    text = json.dumps(result.model_dump(), default=str)
    assert not RAW.search(text)


def test_fixtures_classified_informational() -> None:
    result = _runner().run()
    # known intentional fixtures (tests/, detector modules) appear as informational
    assert result.findings_summary.informational >= 1
    for f in result.findings:
        if f.severity == "critical":
            raise AssertionError(f"unexpected confirmed secret: {f.file_path}")
