#!/usr/bin/env python3
"""Step 54.3 -- container runtime security alignment verifier.

Marker: CONTAINER_RUNTIME_SECURITY_ALIGNMENT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "container-runtime-security-alignment.yaml"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not F.is_file():
        bad(f"missing {F}")
        print("CONTAINER_RUNTIME_SECURITY_ALIGNMENT_VERIFY: FAIL")
        return 1
    a = (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("runtimeAlignment", {})
    sc = a.get("helmSecurityContextBaseline", {})
    if not sc.get("runAsNonRoot") or not sc.get("readOnlyRootFilesystem"):
        bad("Step 51 securityContext baseline not mapped (runAsNonRoot/readOnlyRoot)")
    else:
        ok("Step 51 securityContext baseline mapped")

    real = a.get("imageReality", {})
    if (
        real.get("dockerfileNonRootComplete") is not False
        or real.get("firstPartyImageUser") != "root"
    ):
        bad("Dockerfile USER gap (root images) not recorded")
    else:
        ok("Dockerfile USER gap recorded (first-party images run as root)")

    gap = a.get("gap", {})
    if not gap.get("staticContextNotEqualImageRuntimeCompatibility"):
        bad("static-context != image-runtime-compatibility gap not stated")
    else:
        ok("static securityContext != image runtime compatibility stated")

    if a.get("clusterSmokeRequired") is not True:
        bad("cluster smoke requirement not recorded")
    else:
        ok("non-production cluster smoke required (Step 55)")

    if a.get("productionReady") is not False:
        bad("productionReady must be false")
    else:
        ok("productionReady false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("CONTAINER_RUNTIME_SECURITY_ALIGNMENT_VERIFY: FAIL")
        return 1
    print("CONTAINER_RUNTIME_SECURITY_ALIGNMENT_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
