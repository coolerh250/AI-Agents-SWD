#!/usr/bin/env python3
"""Step 54.2 -- security scan result normalization verifier.

Asserts the normalizer produces a unified redacted summary, maps severities,
preserves tool_unavailable, treats a missing scan as not clean, and never marks
production ready.

Marker: SECURITY_SCAN_RESULT_NORMALIZATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.sdk.security_findings import (  # noqa: E402
    FindingsSummary,
    ScanResult,
    SecurityFinding,
    make_finding_id,
    normalize,
    redact_report,
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
    # synthetic: secret completed clean, sast tool_unavailable, dependency missing
    secret = ScanResult(scan_type="secret", scanner="custom_repo_secret_scan", status="passed")
    sast = ScanResult(
        scan_type="sast",
        scanner="bandit",
        status="tool_unavailable",
        limitations=["bandit_not_available_runtime_detected"],
    )
    summary = normalize({"secret": secret, "sast": sast, "dependency": None})

    for key in ("schema_version", "per_type", "totals", "production_ready", "not_ready_reasons"):
        if key not in summary:
            bad(f"unified summary missing key: {key}")
    if not [f for f in failures if "missing key" in f]:
        ok("unified summary schema present")

    if summary["per_type"]["sast"]["status"] != "tool_unavailable":
        bad("tool_unavailable not preserved in summary")
    else:
        ok("tool_unavailable preserved")

    if summary["per_type"]["dependency"]["status"] != "not_run":
        bad("missing scan not recorded as not_run")
    elif "dependency_not_run" not in summary["not_ready_reasons"]:
        bad("missing scan not reflected in not_ready_reasons (would imply clean)")
    else:
        ok("missing scan treated as not clean (not_run)")

    if summary["production_ready"] is not False:
        bad("summary productionReady must be false")
    else:
        ok("summary productionReady=false")

    # severity rollup: a critical finding must roll up + flag a production blocker
    crit = SecurityFinding(
        finding_id=make_finding_id("x", "secret", "r", "p", 1),
        scanner="x",
        category="secret",
        severity="critical",
        title="t",
        production_blocker=True,
    )
    sr = ScanResult(
        scan_type="secret",
        scanner="x",
        status="completed_with_findings",
        findings=[crit],
        findings_summary=FindingsSummary.from_findings([crit]),
    )
    sm2 = normalize({"secret": sr, "sast": None, "dependency": None})
    if sm2["totals"]["critical"] != 1 or not sm2["production_blocker"]:
        bad("critical finding not rolled up / not flagged as production blocker")
    else:
        ok("severity rollup + production_blocker mapping correct")

    # redaction: a JWT in evidence must not survive into the serialized summary
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    leaky = SecurityFinding(
        finding_id=make_finding_id("x", "secret", "r", "p", 2),
        scanner="x",
        category="secret",
        severity="informational",
        title="t",
        evidence_redacted=jwt,
    )
    lr = ScanResult(
        scan_type="secret",
        scanner="x",
        status="completed_with_findings",
        findings=[leaky],
        findings_summary=FindingsSummary.from_findings([leaky]),
    )
    text = json.dumps(redact_report(normalize({"secret": lr, "sast": None, "dependency": None})))
    if jwt in text:
        bad("raw JWT survived into normalized summary")
    else:
        ok("secret evidence redacted in normalized summary")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_SCAN_RESULT_NORMALIZATION_VERIFY: FAIL")
        return 1
    print("SECURITY_SCAN_RESULT_NORMALIZATION_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
