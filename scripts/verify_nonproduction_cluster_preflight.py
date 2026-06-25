#!/usr/bin/env python3
"""Step 55 -- non-production cluster preflight verifier.

Detects whether a SAFE non-production Kubernetes cluster is reachable (kubectl +
helm + kubeconfig + non-production context). Never prints a kubeconfig / token /
cert / context name. When no safe cluster exists it honestly reports BLOCKED
(never a faked PASS).

Marker: NONPROD_CLUSTER_PREFLIGHT_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402

MARKER = "NONPROD_CLUSTER_PREFLIGHT_VERIFY"
PLAN = ROOT / "infra" / "kubernetes" / "nonproduction-cluster-smoke-plan.yaml"


def main() -> int:
    if not PLAN.is_file():
        print("  [FAIL] missing nonproduction-cluster-smoke-plan.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] non-production cluster smoke plan present")

    available, safe, reason = detect_cluster()
    print(f"  cluster available={available} safe={safe} reason={reason}")
    if not available:
        print("  [BLOCKED] no non-production cluster access (no fake smoke)")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    if not safe:
        # Production-like or unsafe context detected: refuse, do not deploy.
        print("  [BLOCKED] cluster context is not safe for a non-production smoke")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    print("  [OK] safe non-production cluster detected")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
