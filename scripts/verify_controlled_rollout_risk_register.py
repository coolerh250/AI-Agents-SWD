#!/usr/bin/env python3
"""Step 63A -- controlled rollout risk register verifier.

Marker: CONTROLLED_ROLLOUT_RISK_REGISTER_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "CONTROLLED_ROLLOUT_RISK_REGISTER_VERIFY"
FIELDS = ("severity", "likelihood", "mitigation", "decision_impact")
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    risks = loaders.load("risk_register").get("risks", [])
    if not risks:
        bad("no risks registered")
    names = {r.get("name") for r in risks}
    for required in (
        "production_target_absent",
        "production_credentials_absent",
        "production_gitops_absent",
        "operator_approval_missing",
    ):
        if required not in names:
            bad(f"missing required risk: {required}")
    for r in risks:
        for f in FIELDS:
            if f not in r:
                bad(f"risk {r.get('name')} missing field {f}")
        if r.get("decision_impact") not in ("go", "conditional_go", "no_go"):
            bad(f"risk {r.get('name')} invalid decision_impact {r.get('decision_impact')}")
    if not any(r.get("decision_impact") == "no_go" for r in risks):
        bad("expected at least one no_go-impacting risk at this stage")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        f"  [OK] risk register: {len(risks)} risks; severity/likelihood/mitigation/decision_impact"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
