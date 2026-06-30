#!/usr/bin/env python3
"""Step 61 -- recovery evidence package verifier.

Marker: RECOVERY_EVIDENCE_PACKAGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.sdk.backup_restore_dr import build_recovery_evidence  # noqa: E402

MARKER = "RECOVERY_EVIDENCE_PACKAGE_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    # Missing required evidence reported.
    ev = build_recovery_evidence({})
    if not ev["missing_required"] or ev["complete"]:
        bad("empty evidence should be incomplete with missing_required")
    if ev["production_ready"] or ev["production_restore_ready"]:
        bad("production_ready / production_restore_ready must be false")

    # Forbidden-key content redacted (no secret / token / kubeconfig / raw dump passthrough).
    ev2 = build_recovery_evidence(
        {
            "backup_inventory": {"ok": 1},
            "operator_decisions": {"token": "x", "kubeconfig": "y", "raw_db_dump": "z"},
        }
    )
    od = ev2["evidence"].get("operator_decisions", {})
    for k in ("token", "kubeconfig", "raw_db_dump"):
        if od.get(k) != "[redacted]":
            bad(f"forbidden key {k} not redacted")

    # Production blocking status is explicit.
    pb = ev2.get("production_blocking_status", {})
    if not pb.get("production_restore_blocked") or not pb.get("production_failover_blocked"):
        bad("production blocking status must be explicit")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] recovery evidence: redacted; missing reported; production not ready")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
