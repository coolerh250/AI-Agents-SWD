#!/usr/bin/env python3
"""Step 54.3 -- SBOM generation boundary verifier.

Marker: SBOM_GENERATION_BOUNDARY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "sbom-generation-boundary.yaml"
MUST_FALSE = [
    "externalUploadAllowed",
    "networkAllowed",
    "tokenAllowed",
    "registryLoginAllowed",
    "imagePushAllowed",
    "imagePullAllowed",
    "productionAttestationAllowed",
    "committedRuntimeReportsAllowed",
]
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
        print("SBOM_GENERATION_BOUNDARY_VERIFY: FAIL")
        return 1
    b = (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("sbomGeneration", {})
    if b.get("localOnly") is not True:
        bad("localOnly must be true")
    else:
        ok("SBOM generation local-only")
    for k in MUST_FALSE:
        if b.get(k) is not False:
            bad(f"{k} must be false")
    if not [f for f in failures if "must be false" in f]:
        ok(
            "no network/upload/token/registry-login/image-push-pull/attestation; reports not committed"
        )
    if b.get("productionReady") is not False:
        bad("productionReady must be false")
    else:
        ok("productionReady false")
    if not b.get("allowedScopes"):
        bad("allowedScopes missing")
    else:
        ok("allowed scopes defined")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SBOM_GENERATION_BOUNDARY_VERIFY: FAIL")
        return 1
    print("SBOM_GENERATION_BOUNDARY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
