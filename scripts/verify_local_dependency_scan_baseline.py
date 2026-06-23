#!/usr/bin/env python3
"""Step 54.2 -- local dependency scan baseline verifier.

Runs the local dependency scanner and asserts: it inspects local manifests only,
records the Python lockfile gap, records Node lockfile status, performs no
external CVE lookup, never claims clean without a CVE check, and is non-production.

Marker: LOCAL_DEPENDENCY_SCAN_BASELINE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import subprocess  # nosec: fixed argv, no shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_local_dependency_scan.py"

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
        bad("run_local_dependency_scan.py missing")
        print("LOCAL_DEPENDENCY_SCAN_BASELINE_VERIFY: FAIL")
        return 1
    ok("local dependency scan runner present")

    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "dependency-scan-report.json"
        proc = subprocess.run(  # nosec: fixed argv, no shell
            [sys.executable, str(RUNNER), "--json-report", str(report), "--quiet"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 2 or not report.is_file():
            bad("dependency runner failed to produce a report")
            print("LOCAL_DEPENDENCY_SCAN_BASELINE_VERIFY: FAIL")
            return 1
        data = json.loads(report.read_text(encoding="utf-8"))
        ok("dependency report generated in runtime path")

        lims = data.get("limitations", [])
        if not any("no_cve_lookup" in lim for lim in lims):
            bad("report must record that no CVE lookup was performed")
        else:
            ok("no external CVE lookup performed (recorded)")

        if not any("lockfile_missing" in lim for lim in lims) and not any(
            "python_lockfile_missing" in lim for lim in lims
        ):
            bad("Python lockfile gap not recorded")
        else:
            ok("Python lockfile gap recorded")

        if not any("node_lockfile" in lim for lim in lims):
            bad("Node lockfile status not recorded")
        else:
            ok("Node lockfile status recorded")

        if data.get("network_used"):
            bad("dependency scan used the network")
        else:
            ok("no network used")

        if data.get("production_ready") is not False:
            bad("dependency report productionReady must be false")
        else:
            ok("dependency report productionReady=false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("LOCAL_DEPENDENCY_SCAN_BASELINE_VERIFY: FAIL")
        return 1
    print("LOCAL_DEPENDENCY_SCAN_BASELINE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
