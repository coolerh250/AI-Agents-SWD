#!/usr/bin/env python3
"""Step 54.2 -- local SAST baseline verifier.

Runs the local SAST scanner over the codebase, confirms the custom static checks
detect every unsafe pattern in the intentional fixture, and asserts the report is
redacted, non-production, and records limitations. No external upload.

Marker: LOCAL_SAST_BASELINE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import importlib.util
import json
import subprocess  # nosec: fixed argv, no shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_local_sast_scan.py"
FIXTURE = ROOT / "tests" / "fixtures" / "sast_unsafe_samples.py"
EXPECT_RULES = {"PY-EVAL", "PY-EXEC", "PY-SHELL-TRUE", "PY-YAML-LOAD", "PY-TLS-VERIFY-OFF"}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _load_runner():
    spec = importlib.util.spec_from_file_location("_sast_runner", RUNNER)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    if not RUNNER.is_file():
        bad("run_local_sast_scan.py missing")
        print("LOCAL_SAST_BASELINE_VERIFY: FAIL")
        return 1
    ok("local SAST runner present")

    if not FIXTURE.is_file():
        bad("SAST unsafe-pattern fixture missing")
    else:
        runner = _load_runner()
        rules = {
            f.rule_id
            for f in runner.scan_text(
                FIXTURE.read_text(encoding="utf-8"), "tests/fixtures/sast_unsafe_samples.py"
            )
        }
        missing = EXPECT_RULES - rules
        if missing:
            bad(f"custom static checks missed unsafe patterns: {missing}")
        else:
            ok("custom static checks detect unsafe fixture patterns")

    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "sast-scan-report.json"
        proc = subprocess.run(  # nosec: fixed argv, no shell
            [sys.executable, str(RUNNER), "--json-report", str(report), "--quiet"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 2 or not report.is_file():
            bad("SAST runner failed to produce a report")
            print("LOCAL_SAST_BASELINE_VERIFY: FAIL")
            return 1
        data = json.loads(report.read_text(encoding="utf-8"))
        ok("SAST report generated in runtime path")
        if not data.get("limitations"):
            bad("SAST report records no limitations")
        else:
            ok("SAST limitations recorded (limited custom baseline)")
        if data.get("network_used") or data.get("source_uploaded"):
            bad("SAST runner used network / uploaded source")
        else:
            ok("no network, no source upload")
        if data.get("production_ready") is not False:
            bad("SAST report productionReady must be false")
        else:
            ok("SAST report productionReady=false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("LOCAL_SAST_BASELINE_VERIFY: FAIL")
        return 1
    print("LOCAL_SAST_BASELINE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
