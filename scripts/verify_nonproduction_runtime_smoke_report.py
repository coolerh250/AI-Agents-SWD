#!/usr/bin/env python3
"""Step 55 -- non-production runtime smoke report verifier.

Validates the committed report SCHEMA (always) and the runtime report IF PRESENT.
The runtime report is never committed and is only produced by a real smoke, so with
no safe cluster it reports BLOCKED_NO_SAFE_CLUSTER.

Marker: NONPROD_RUNTIME_SMOKE_REPORT_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NONPROD_RUNTIME_SMOKE_REPORT_VERIFY"
SCHEMA = ROOT / "infra" / "kubernetes" / "nonproduction-runtime-smoke-report-schema.yaml"
REPORT = ROOT / ".runtime" / "kubernetes" / "nonproduction-runtime-smoke-report.json"
SECRET_SHAPES = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|"
    r"apiVersion:|kind:\s*Deployment)"
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not SCHEMA.is_file():
        bad("missing nonproduction-runtime-smoke-report-schema.yaml")
    else:
        s = (yaml.safe_load(SCHEMA.read_text(encoding="utf-8")) or {}).get(
            "nonProductionRuntimeSmokeReportSchema", {}
        )
        if s.get("productionReady") is not False:
            bad("schema productionReady must be false")
        if s.get("committedRuntimeReportAllowed") is not False:
            bad("schema must forbid committing the runtime report")
        red = s.get("redaction", {})
        if not all(
            red.get(k) is True
            for k in ("noKubeconfig", "noToken", "noSecret", "noRenderedManifest")
        ):
            bad("schema redaction rules incomplete")
        if not failures:
            print(
                "  [OK] report schema valid; productionReady false; redaction enforced; not committed"
            )

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    if not REPORT.is_file():
        print("  [BLOCKED] no runtime smoke report (no safe cluster / smoke not run)")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0

    try:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"{MARKER}: FAIL")
        return 1
    if report.get("productionReady") is not False or report.get("productionExecuted") is not False:
        bad("runtime report must be productionReady=false, productionExecuted=false")
    if SECRET_SHAPES.search(json.dumps(report)):
        bad("runtime report contains a secret / kubeconfig / rendered manifest shape")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] runtime report present, redacted, non-production")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
