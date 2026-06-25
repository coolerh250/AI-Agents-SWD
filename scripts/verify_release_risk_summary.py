#!/usr/bin/env python3
"""Step 54.4 -- release risk summary verifier.

Generates the release risk summary and asserts it is NOT a production / deployment
approval, the status is within the allowed enum (never production_ready), missing
required evidence forces not_ready, and productionReady is false.

Marker: RELEASE_RISK_SUMMARY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_release_risk_summary import build_release_risk_summary  # noqa: E402

ALLOWED = {"not_ready", "ready_for_non_production_review", "ready_for_operator_review", "blocked"}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    summ = build_release_risk_summary()
    out = ROOT / ".runtime" / "security" / "release-risk-summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summ, indent=2, sort_keys=True), encoding="utf-8")

    status = summ.get("status")
    if status not in ALLOWED:
        bad(f"status not in allowed enum: {status!r}")
    elif status in ("production_ready", "production_approved"):
        bad(f"forbidden status: {status!r}")
    else:
        ok(f"status={status} (within allowed enum)")

    if summ.get("productionReady") is not False:
        bad("productionReady must be false")
    else:
        ok("productionReady=false")
    if summ.get("productionApproval") is not False:
        bad("productionApproval must be false")
    else:
        ok("productionApproval=false")
    if summ.get("deploymentApproval") is not False:
        bad("deploymentApproval must be false")
    else:
        ok("deploymentApproval=false")

    if summ.get("scoreIsNotApproval") is not True:
        bad("scoreIsNotApproval must be true")
    else:
        ok("score is explicitly not an approval")

    # Missing required production evidence => not_ready (or blocked on critical).
    if summ.get("missingEvidence") and status not in ("not_ready", "blocked"):
        bad(f"missing evidence present but status={status} (expected not_ready/blocked)")
    else:
        ok("missing evidence forces not_ready/blocked")

    if not summ.get("blockers"):
        bad("blockers empty")
    else:
        ok(f"{len(summ['blockers'])} blockers listed")

    blob = json.dumps(summ).lower()
    if "production_ready" in blob or "production_approved" in blob:
        bad("summary contains production_ready/production_approved text")
    else:
        ok("no production_ready/production_approved text")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("RELEASE_RISK_SUMMARY_VERIFY: FAIL")
        return 1
    print("RELEASE_RISK_SUMMARY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
