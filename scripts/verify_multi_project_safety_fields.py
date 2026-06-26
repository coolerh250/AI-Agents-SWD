#!/usr/bin/env python3
"""Step 57 -- multi-project safety fields verifier (live /operations/safety)."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

MARKER = "MULTI_PROJECT_SAFETY_FIELDS_VERIFY"
URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000") + "/operations/safety"

EXPECTED = {
    "multi_project_enabled": True,
    "multi_project_write_api_enabled": True,
    "work_item_dispatch_enabled": True,
    "work_item_dispatch_external_side_effect_enabled": False,
    "work_item_dispatch_github_write_enabled": False,
    "work_item_dispatch_argocd_sync_enabled": False,
    "work_item_dispatch_production_action_enabled": False,
    "work_item_delivery_package_linkage_enabled": True,
    "work_item_project_audit_enabled": True,
    "work_item_notification_external_send_enabled": False,
    "multi_project_production_ready": False,
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
    print("  [OK] multi-project safety fields non-production; production_executed_true_count=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
