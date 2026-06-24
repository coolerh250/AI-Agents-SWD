#!/usr/bin/env python3
"""Step 54.3 -- local SBOM baseline verifier.

Runs the local SBOM runner and asserts: it generates a redacted runtime report
covering Python / Node / container images, records the Python lockfile gap and
unpinned-digest limitation, leaks no secret, and is non-production.

Marker: LOCAL_SBOM_BASELINE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec: fixed argv, no shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_local_sbom_baseline.py"
RAW = re.compile(r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY)")

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
        bad("run_local_sbom_baseline.py missing")
        print("LOCAL_SBOM_BASELINE_VERIFY: FAIL")
        return 1
    ok("local SBOM runner present")

    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "sbom.json"
        proc = subprocess.run(  # nosec: fixed argv, no shell
            [sys.executable, str(RUNNER), "--json-report", str(report), "--quiet"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 2 or not report.is_file():
            bad("SBOM runner failed to produce a report")
            print("LOCAL_SBOM_BASELINE_VERIFY: FAIL")
            return 1
        data = json.loads(report.read_text(encoding="utf-8"))
        ok("redacted SBOM report generated in runtime path")

        scopes = set(data.get("scope", []))
        if not {"python_manifest", "node_manifest", "container_image_inventory"} <= scopes:
            bad("SBOM does not cover python/node/container scopes")
        else:
            ok("SBOM covers python + node + container image inventory")

        types = {c.get("type") for c in data.get("components", [])}
        if not {"python", "container_image"} <= types:
            bad(f"SBOM components missing expected types: {types}")
        else:
            ok("SBOM includes python + container image components")

        lims = " ".join(data.get("limitations", []))
        if "python_lockfile_missing" not in lims:
            bad("missing Python lockfile not recorded")
        if "not_digest_pinned" not in lims and "digest" not in lims:
            bad("unpinned image digest limitation not recorded")
        if not [f for f in failures if "lockfile" in f or "digest" in f]:
            ok("Python lockfile gap + unpinned digest limitation recorded")

        text = report.read_text(encoding="utf-8")
        if RAW.search(text):
            bad("SBOM report contains a raw credential value")
        else:
            ok("no raw credential value in SBOM report")
        if data.get("productionReady") is not False:
            bad("SBOM productionReady must be false")
        else:
            ok("SBOM productionReady=false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("LOCAL_SBOM_BASELINE_VERIFY: FAIL")
        return 1
    print("LOCAL_SBOM_BASELINE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
