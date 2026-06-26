#!/usr/bin/env python3
"""Step 55 -- service health smoke verifier.

Cluster-runtime smoke: requires a SAFE non-production cluster. With no safe cluster
it reports BLOCKED_NO_SAFE_CLUSTER (never a faked PASS). When a safe cluster is
present the real checks run against the aiagents-smoke-* namespace:
orchestrator / policy-engine / approval-engine / audit-service / communication-gateway / agents /health via port-forward or an in-cluster curl job (no public ingress, no LoadBalancer).

Marker: NONPROD_SERVICE_HEALTH_SMOKE_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402
from scripts.lib.nonprod_smoke_report import section_status  # noqa: E402

MARKER = "NONPROD_SERVICE_HEALTH_SMOKE_VERIFY"
SECTION = "serviceHealth"


def main() -> int:
    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] service health smoke requires a safe non-production cluster ({reason})")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    # Safe non-production cluster present: PASS reflects the REAL live smoke report
    # (services have endpoints; readiness probes on /health pass). No report yet ->
    # smoke not run -> BLOCKED (never a faked PASS).
    status = section_status(SECTION)
    if status is None:
        print("  [BLOCKED] no runtime smoke report yet (run run_nonproduction_runtime_smoke.py)")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    if status == "pass":
        print(f"  [OK] live cluster smoke section '{SECTION}' passed")
        print(f"{MARKER}: PASS")
        return 0
    print(f"  [FAIL] live cluster smoke section '{SECTION}' status={status}")
    print(f"{MARKER}: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
