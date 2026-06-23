#!/usr/bin/env python3
"""Step 54.1 -- security gate fail-closed policy verifier.

Asserts the gate policy exists, is fail-closed, treats missing evidence as
not-ready, fails on confirmed secret leak + critical findings, keeps the
production gate disabled, and introduces no release-gate mutation.

Marker: SECURITY_GATE_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SDIR = ROOT / "infra" / "security"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    gp = SDIR / "security-gate-fail-closed-policy.yaml"
    tx = SDIR / "security-finding-taxonomy.yaml"
    if not gp.is_file():
        bad("missing security-gate-fail-closed-policy.yaml")
        print("SECURITY_GATE_POLICY_VERIFY: FAIL")
        return 1
    gate = (yaml.safe_load(gp.read_text(encoding="utf-8")) or {}).get("gate", {})
    taxonomy = yaml.safe_load(tx.read_text(encoding="utf-8")) or {} if tx.is_file() else {}

    if gate.get("failClosed") is not True:
        bad("gate.failClosed must be true")
    else:
        ok("fail-closed policy exists")

    missing = gate.get("missingEvidenceBehavior", {})
    if not missing or any(v != "not_ready" for v in missing.values()):
        bad("missing evidence must map to not_ready")
    else:
        ok("missing evidence => not ready")

    fb = gate.get("findingBehavior", {})
    if fb.get("confirmedSecretLeak") != "fail":
        bad("confirmed secret leak must fail")
    if fb.get("criticalFinding") != "fail":
        bad("critical finding must fail")
    if not [f for f in failures if "secret leak" in f or "critical finding" in f]:
        ok("confirmed secret leak fail; critical finding fail")

    if gate.get("productionGateEnabled") is not False:
        bad("productionGateEnabled must be false")
    if gate.get("releaseGateMutationEnabled") is not False:
        bad("releaseGateMutationEnabled must be false")
    if not [f for f in failures if "Gate" in f and "must be false" in f]:
        ok("production gate disabled; no release gate mutation")

    # taxonomy: secret leak / production credential leak / unauthenticated deploy = critical
    specials = {s.get("condition"): s for s in taxonomy.get("specialClassifications", [])}
    for cond in ("secret_leak", "production_credential_leak", "unauthenticated_deploy_path"):
        if specials.get(cond, {}).get("severity") != "critical":
            bad(f"{cond} must be classified critical")
    if not [f for f in failures if "critical" in f and "classified" in f]:
        ok("secret leak / prod credential leak / unauth deploy classified critical")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_GATE_POLICY_VERIFY: FAIL")
        return 1
    print("SECURITY_GATE_POLICY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
