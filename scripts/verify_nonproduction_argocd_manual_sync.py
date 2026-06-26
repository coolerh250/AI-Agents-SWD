#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD manual-sync verifier.

Consumes the live redacted manual-sync report (produced by
run_nonproduction_argocd_manual_sync_report.py). PASS requires a REAL manual sync:
Synced + Healthy, manual-only (no auto-sync / prune / self-heal), destination
aiagents-smoke-dev, no production namespace touched. No report -> BLOCKED (the sync
has not run); never a faked PASS.

Marker: NONPROD_ARGOCD_MANUAL_SYNC_VERIFY: PASS | BLOCKED | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.argocd_sync_report import load_report  # noqa: E402

MARKER = "NONPROD_ARGOCD_MANUAL_SYNC_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    report = load_report()
    if report is None:
        print("  [BLOCKED] no manual-sync report yet (run the manual sync first)")
        print(f"{MARKER}: BLOCKED")
        return 0

    sync = report.get("sync", {})
    if sync.get("status") != "Synced":
        bad(f"sync status is not Synced ({sync.get('status')})")
    if report.get("health", {}).get("status") != "Healthy":
        bad(f"health is not Healthy ({report.get('health', {}).get('status')})")
    if report.get("operation", {}).get("phase") != "Succeeded":
        bad("last operation did not succeed")
    if sync.get("manualOnly") is not True or sync.get("autoSyncEnabled") is not False:
        bad("sync must be manual-only (no auto-sync)")
    if sync.get("pruneEnabled") is not False:
        bad("prune must be disabled")
    if sync.get("selfHealEnabled") is not False:
        bad("self-heal must be disabled")
    if report.get("destinationNamespace") != "aiagents-smoke-dev":
        bad("destination namespace must be aiagents-smoke-dev")
    if report.get("productionNamespaceTouched") is not False:
        bad("a production namespace was touched")
    if report.get("argocdProductionSyncPerformed") is not False:
        bad("argocd production sync must be false")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] real manual sync Synced + Healthy; manual-only; non-production destination")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
