#!/usr/bin/env python3
"""Step 63A -- production target assessment verifier.

Marker: PRODUCTION_TARGET_ASSESSMENT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "PRODUCTION_TARGET_ASSESSMENT_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    t = loaders.load("target")
    if t.get("productionTargetExists") is not False:
        bad("production target must not be claimed to exist")
    if t.get("kindNonprodIsProductionCluster") is not False:
        bad("kind nonprod must not be a production cluster")
    if t.get("nonprodArgocdIsProductionArgocd") is not False:
        bad("nonprod ArgoCD must not be a production ArgoCD")
    missing = loaders.missing_target_items()
    if not missing:
        bad("expected production target items to be missing (not faked)")
    if t.get("status") not in ("missing", "insufficient"):
        bad(f"target status should be missing/insufficient, got {t.get('status')}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] production target: {len(missing)} items missing; no production env faked")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
