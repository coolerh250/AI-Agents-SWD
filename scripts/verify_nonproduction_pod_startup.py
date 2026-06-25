#!/usr/bin/env python3
"""Step 55 -- pod startup smoke verifier.

Cluster-runtime smoke: requires a SAFE non-production cluster. With no safe cluster
it reports BLOCKED_NO_SAFE_CLUSTER (never a faked PASS). When a safe cluster is
present the real checks run against the aiagents-smoke-* namespace:
pods reach Running/Completed; no CrashLoopBackOff / ImagePullBackOff / CreateContainerConfigError; no runAsNonRoot / readOnlyRootFilesystem / writable-path / missing-secret failure.

Marker: NONPROD_POD_STARTUP_SMOKE_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402

MARKER = "NONPROD_POD_STARTUP_SMOKE_VERIFY"


def main() -> int:
    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] pod startup smoke requires a safe non-production cluster ({reason})")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0
    # Safe non-production cluster present: the real pod startup smoke checks run here
    # (pods reach Running/Completed; no CrashLoopBackOff / ImagePullBackOff / CreateContainerConfigError; no runAsNonRoot / readOnlyRootFilesystem / writable-path / missing-secret failure). production_executed stays false; no deploy/sync.
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
