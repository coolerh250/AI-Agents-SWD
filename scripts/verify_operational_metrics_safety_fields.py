#!/usr/bin/env python3
"""Step 58 -- operational metrics safety fields verifier (live).

Marker: OPERATIONAL_METRICS_SAFETY_FIELDS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "OPERATIONAL_METRICS_SAFETY_FIELDS_VERIFY"
URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

EXPECTED = {
    "admin_console_v2_metrics_enabled": True,
    "operational_metrics_snapshot_generated": True,
    "operational_metrics_external_side_effect_enabled": False,
    "operational_metrics_gitops_sync_enabled": False,
    "operational_metrics_kubernetes_mutation_enabled": False,
    "operational_metrics_github_write_enabled": False,
    "operational_metrics_external_send_enabled": False,
    "operational_metrics_production_action_enabled": False,
    "operational_metrics_production_ready": False,
    "production_executed_true_count": 0,
}
failures: list[str] = []


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=10) as r:  # noqa: S310
            data = json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"  [FAIL] could not read {URL}: {exc}")
        print(f"{MARKER}: FAIL")
        return 1
    for key, want in EXPECTED.items():
        if data.get(key) != want:
            failures.append(key)
            print(f"  [FAIL] {key}={data.get(key)!r} (expected {want!r})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] operational metrics safety fields: visibility-only; production_executed=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
