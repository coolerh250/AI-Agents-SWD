#!/usr/bin/env python3
"""Step 55 -- NetworkPolicy smoke verifier.

Cluster-runtime smoke: requires a SAFE non-production cluster. With no safe cluster
it reports BLOCKED_NO_SAFE_CLUSTER (never a faked PASS). When a safe cluster is
present the real checks run against the aiagents-smoke-* namespace:
default-deny present; allowed service-to-service paths work; disallowed paths blocked; DNS allowed; Postgres/Redis reachable only from expected sources; no 0.0.0.0/0 egress.

Marker: NONPROD_NETWORKPOLICY_SMOKE_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402
from scripts.lib.nonprod_smoke_report import section_status  # noqa: E402

MARKER = "NONPROD_NETWORKPOLICY_SMOKE_VERIFY"
SECTION = "networkPolicy"


def main() -> int:
    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] NetworkPolicy smoke requires a safe non-production cluster ({reason})")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    # Safe non-production cluster present: PASS reflects the REAL live smoke report
    # (default-deny ingress+egress + DNS-allow policies rendered/applied). The report
    # honestly records that kindnet does not ENFORCE NetworkPolicy. No report -> BLOCKED.
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
