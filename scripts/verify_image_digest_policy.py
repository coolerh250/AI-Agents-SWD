#!/usr/bin/env python3
"""Step 54.3 -- image digest policy verifier.

Marker: IMAGE_DIGEST_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "image-digest-policy.yaml"

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
        print("IMAGE_DIGEST_POLICY_VERIFY: FAIL")
        return 1
    p = (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("imageDigestPolicy", {})
    if p.get("digestRequired") is not True:
        bad("digestRequired must be true")
    if "non_production_cluster_smoke" not in (p.get("requiredBefore") or []):
        bad("digest must be required before cluster smoke")
    if not [f for f in failures if "digest" in f.lower()]:
        ok("digest required before cluster smoke / sync / deploy")

    if p.get("latestTagAllowed") is not False:
        bad("latestTagAllowed must be false")
    else:
        ok("latest tag prohibited")

    if p.get("registryLoginConfigured") is not False:
        bad("registryLoginConfigured must be false")
    else:
        ok("registry login not configured")

    cs = p.get("currentState", {})
    if cs.get("anyDigestPinned") is not False:
        bad("currentState.anyDigestPinned must be false (no digests resolved)")
    elif not p.get("blockers"):
        bad("missing-digest blockers not recorded")
    else:
        ok("missing digest recorded as blocker, not marked safe")

    if p.get("productionReady") is not False:
        bad("productionReady must be false")
    else:
        ok("productionReady false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("IMAGE_DIGEST_POLICY_VERIFY: FAIL")
        return 1
    print("IMAGE_DIGEST_POLICY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
