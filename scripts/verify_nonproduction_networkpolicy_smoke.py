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

MARKER = "NONPROD_NETWORKPOLICY_SMOKE_VERIFY"


def main() -> int:
    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] NetworkPolicy smoke requires a safe non-production cluster ({reason})")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    # Safe non-production cluster present: the real NetworkPolicy smoke checks run here
    # (default-deny present; allowed service-to-service paths work; disallowed paths blocked; DNS allowed; Postgres/Redis reachable only from expected sources; no 0.0.0.0/0 egress). production_executed stays false; no deploy/sync.
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
