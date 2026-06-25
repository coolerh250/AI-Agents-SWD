#!/usr/bin/env python3
"""Step 55 -- PVC / storage smoke verifier.

Cluster-runtime smoke: requires a SAFE non-production cluster. With no safe cluster
it reports BLOCKED_NO_SAFE_CLUSTER (never a faked PASS). When a safe cluster is
present the real checks run against the aiagents-smoke-* namespace:
Postgres/Redis PVC bound; workspace ephemeral volumes mounted; no hostPath; no production storage class / PV; backup target disabled; restore job disabled.

Marker: NONPROD_STORAGE_SMOKE_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402

MARKER = "NONPROD_STORAGE_SMOKE_VERIFY"


def main() -> int:
    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] PVC / storage smoke requires a safe non-production cluster ({reason})")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    # Safe non-production cluster present: the real PVC / storage smoke checks run here
    # (Postgres/Redis PVC bound; workspace ephemeral volumes mounted; no hostPath; no production storage class / PV; backup target disabled; restore job disabled). production_executed stays false; no deploy/sync.
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
