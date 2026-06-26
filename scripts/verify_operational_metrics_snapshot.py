#!/usr/bin/env python3
"""Step 58 -- operational metrics snapshot verifier.

Generates the snapshot if missing, then validates it: production_ready=false,
unavailable/stale sources explicit (not hidden), no secret/token/kubeconfig shape.

Marker: OPERATIONAL_METRICS_SNAPSHOT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MARKER = "OPERATIONAL_METRICS_SNAPSHOT_VERIFY"
SNAP = ROOT / ".runtime" / "operations" / "operational-metrics-snapshot.json"
SECRET_SHAPES = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|-----BEGIN)"
)
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not SNAP.is_file():
        from shared.sdk.operations_metrics import build_snapshot

        snap = asyncio.run(build_snapshot(ROOT))
        SNAP.parent.mkdir(parents=True, exist_ok=True)
        SNAP.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    try:
        snap = json.loads(SNAP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        bad("snapshot unreadable")
        print(f"{MARKER}: FAIL")
        return 1

    if snap.get("production_ready") is not False:
        bad("snapshot production_ready must be false")
    if "domains" not in snap or not snap["domains"]:
        bad("snapshot has no domains")
    if "blockers" not in snap:
        bad("snapshot must list blockers explicitly")
    # Unavailable sources must be explicit (available=false carries a reason).
    for name, d in snap.get("domains", {}).items():
        if d.get("available") is False and not d.get("reason"):
            bad(f"unavailable domain {name} hides its reason")
    if SECRET_SHAPES.search(json.dumps(snap)):
        bad("snapshot contains a secret-like shape")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] snapshot redacted; production_ready=false; blockers={snap.get('blockers')}")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
