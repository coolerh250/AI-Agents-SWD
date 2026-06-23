#!/usr/bin/env python3
"""Step 54.2 -- local secret scan baseline verifier.

Runs the local secret scanner and asserts: it executes locally, writes a redacted
JSON report to a runtime path, leaks no raw credential value, fails on a confirmed
finding, and is never marked clean when the tool is unavailable.

Marker: LOCAL_SECRET_SCAN_BASELINE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec: fixed argv, no shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_local_secret_scan.py"
RAW_SECRET = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}|BEGIN [A-Z ]*PRIVATE KEY)"
)

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not RUNNER.is_file():
        bad("run_local_secret_scan.py missing")
        print("LOCAL_SECRET_SCAN_BASELINE_VERIFY: FAIL")
        return 1
    ok("local secret scan runner present")

    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "secret-scan-report.json"
        proc = subprocess.run(  # nosec: fixed argv, no shell
            [sys.executable, str(RUNNER), "--json-report", str(report), "--quiet"],
            capture_output=True,
            text=True,
        )
        if not report.is_file():
            bad("runner did not produce a JSON report")
            print("LOCAL_SECRET_SCAN_BASELINE_VERIFY: FAIL")
            return 1
        ok("redacted JSON report generated in runtime path")
        text = report.read_text(encoding="utf-8")
        data = json.loads(text)

        if proc.returncode == 2 or data.get("status") in ("tool_unavailable", "config_error"):
            bad("scanner unavailable / config error must not be a clean PASS")
        else:
            ok("scanner ran locally (not tool_unavailable)")

        if RAW_SECRET.search(text):
            bad("report contains a raw credential value")
        else:
            ok("no raw credential value in report")

        summary = data.get("findings_summary", {})
        confirmed = summary.get("critical", 0) + summary.get("high", 0)
        if confirmed and proc.returncode == 0:
            bad("confirmed secret findings present but exit code is 0")
        if confirmed:
            bad(f"confirmed secret findings present: {confirmed}")
        else:
            ok("no confirmed secret findings (exit 0)")

        if data.get("production_ready") is not False:
            bad("report productionReady must be false")
        else:
            ok("report productionReady=false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("LOCAL_SECRET_SCAN_BASELINE_VERIFY: FAIL")
        return 1
    print("LOCAL_SECRET_SCAN_BASELINE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
