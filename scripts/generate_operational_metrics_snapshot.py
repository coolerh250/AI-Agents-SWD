#!/usr/bin/env python3
"""Step 58 -- generate the operational metrics snapshot (read-only).

Aggregates read-only sources into a redacted snapshot at
``.runtime/operations/operational-metrics-snapshot.json`` (gitignored, NEVER
committed). No mutation, no sync, no deploy, no external call. productionReady=false.

Marker: OPERATIONAL_METRICS_SNAPSHOT_RUN: PASS | FAIL
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.sdk.operations_metrics import build_snapshot  # noqa: E402

MARKER = "OPERATIONAL_METRICS_SNAPSHOT_RUN"
OUT = ROOT / ".runtime" / "operations" / "operational-metrics-snapshot.json"


def main() -> int:
    snapshot = asyncio.run(build_snapshot(ROOT))
    if snapshot.get("production_ready") is not False:
        print("  [FAIL] snapshot must have production_ready=false")
        print(f"{MARKER}: FAIL")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    avail = [k for k, v in snapshot["domains"].items() if v.get("available") is not False]
    print(
        f"  domains available: {len(avail)}/{len(snapshot['domains'])}; blockers={snapshot['blockers']}"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
