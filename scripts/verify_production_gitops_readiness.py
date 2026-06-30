#!/usr/bin/env python3
"""Step 63A -- production GitOps readiness verifier.

Marker: PRODUCTION_GITOPS_READINESS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.controlled_rollout import loaders  # noqa: E402

MARKER = "PRODUCTION_GITOPS_READINESS_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    g = loaders.load("gitops")
    if g.get("nonprodArgocdIsProductionReady") is not False:
        bad("nonprod ArgoCD must not be marked production ready")
    if g.get("creates_production_argocd_app") is not False:
        bad("must not create a production ArgoCD app")
    if g.get("triggers_sync") is not False:
        bad("must not trigger a sync")
    if g.get("applies_manifest") is not False:
        bad("must not apply a manifest")
    missing = loaders.missing_gitops_items()
    if not missing:
        bad("expected production GitOps items to be missing")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] GitOps readiness: {len(missing)} items missing; no app create/sync/apply")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
