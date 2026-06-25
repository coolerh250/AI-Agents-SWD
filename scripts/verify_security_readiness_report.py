#!/usr/bin/env python3
"""Step 54.4 -- security readiness report verifier.

Generates the readiness report and asserts it is non-production: productionReady
false, release gate disabled, production blockers listed, next steps reference the
Step 55 cluster smoke / Step 56 ArgoCD sync.

Marker: SECURITY_READINESS_REPORT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_security_readiness_report import build_security_readiness_report  # noqa: E402

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    rep = build_security_readiness_report()
    out = ROOT / ".runtime" / "security" / "security-readiness-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, sort_keys=True), encoding="utf-8")

    if rep.get("productionReady") is not False:
        bad("productionReady must be false")
    else:
        ok("productionReady=false")
    if rep.get("releaseGateEnabled") is not False:
        bad("releaseGateEnabled must be false")
    else:
        ok("releaseGateEnabled=false")

    if not rep.get("productionBlockers"):
        bad("productionBlockers empty")
    else:
        ok(f"{len(rep['productionBlockers'])} production blockers listed")
    if not rep.get("nonProductionLimitations"):
        bad("nonProductionLimitations empty")
    else:
        ok("non-production limitations listed")

    nxt = rep.get("nextRequiredSteps", [])
    if (
        "step_55_non_production_cluster_smoke" not in nxt
        or "step_56_real_argocd_manual_sync" not in nxt
    ):
        bad("nextRequiredSteps must include Step 55 + Step 56")
    else:
        ok("next steps include Step 55 cluster smoke + Step 56 ArgoCD sync")

    if rep.get("releaseRiskStatus") in ("production_ready", "production_approved"):
        bad(f"releaseRiskStatus forbidden: {rep.get('releaseRiskStatus')}")
    else:
        ok(f"releaseRiskStatus={rep.get('releaseRiskStatus')}")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_READINESS_REPORT_VERIFY: FAIL")
        return 1
    print("SECURITY_READINESS_REPORT_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
