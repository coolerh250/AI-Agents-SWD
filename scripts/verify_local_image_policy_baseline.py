#!/usr/bin/env python3
"""Step 54.3 -- local image policy baseline verifier.

Runs the local image policy scanner and asserts it detects digest + Dockerfile
root gaps, performs no registry login / image pull/push, and is non-production.

Marker: LOCAL_IMAGE_POLICY_BASELINE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import subprocess  # nosec: fixed argv, no shell
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_local_image_policy_scan.py"

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
        bad("run_local_image_policy_scan.py missing")
        print("LOCAL_IMAGE_POLICY_BASELINE_VERIFY: FAIL")
        return 1
    ok("local image policy runner present")

    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "image-policy.json"
        proc = subprocess.run(  # nosec: fixed argv, no shell
            [sys.executable, str(RUNNER), "--json-report", str(report), "--quiet"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 2 or not report.is_file():
            bad("image policy runner failed to produce a report")
            print("LOCAL_IMAGE_POLICY_BASELINE_VERIFY: FAIL")
            return 1
        data = json.loads(report.read_text(encoding="utf-8"))
        ok("local image policy report generated")

        rules = {f.get("rule_id") for f in data.get("policyFindings", [])}
        if "IMG-NO-DIGEST" not in rules:
            bad("digest gaps not detected")
        if "IMG-DOCKERFILE-ROOT" not in rules:
            bad("Dockerfile root gaps not detected")
        if not [f for f in failures if "gaps not detected" in f]:
            ok("digest gaps + Dockerfile root gaps detected")

        if data.get("networkUsed") or data.get("registryLoginUsed"):
            bad("image policy scan used network / registry login")
        else:
            ok("no registry login, no network, no image pull/push")

        lims = " ".join(data.get("limitations", []))
        if "no_cve_lookup" not in lims:
            bad("no-CVE-lookup limitation not recorded")
        else:
            ok("policy-only (no CVE lookup) recorded")

        if data.get("productionReady") is not False:
            bad("image policy report productionReady must be false")
        else:
            ok("image policy report productionReady=false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("LOCAL_IMAGE_POLICY_BASELINE_VERIFY: FAIL")
        return 1
    print("LOCAL_IMAGE_POLICY_BASELINE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
