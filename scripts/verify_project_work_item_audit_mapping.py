#!/usr/bin/env python3
"""Step 57 -- project / work-item audit mapping verifier."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.sdk.work_items.events import build_audit_metadata  # noqa: E402

MARKER = "PROJECT_WORK_ITEM_AUDIT_MAPPING_VERIFY"
MAP = ROOT / "infra" / "delivery" / "project-work-item-audit-mapping.yaml"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    d = (yaml.safe_load(MAP.read_text(encoding="utf-8")) or {}).get(
        "projectWorkItemAuditMapping", {}
    )
    required_events = {
        "project_created",
        "work_item_created",
        "work_item_dispatched",
        "work_item_blocked",
        "work_item_completed",
        "delivery_package_linked",
    }
    if not required_events <= set(d.get("events", [])):
        bad("missing required audit events")
    if not {"actor", "role", "reason", "project_id", "correlation_id"} <= set(
        d.get("requiredMetadata", [])
    ):
        bad("requiredMetadata incomplete")
    for k in ("secret", "token", "chain_of_thought"):
        if k not in d.get("forbiddenMetadata", []):
            bad(f"forbiddenMetadata missing: {k}")

    # build_audit_metadata drops forbidden keys + keeps production_executed false
    meta = build_audit_metadata(
        event_type="work_item_dispatched",
        actor="a",
        role="operator",
        reason="r",
        project_id="p",
        work_item_id="w",
        correlation_id="c",
        extra={"secret": "x", "token": "y", "chain_of_thought": "z", "note": "ok"},
    )
    for forbidden in ("secret", "token", "chain_of_thought"):
        if forbidden in meta:
            bad(f"audit metadata leaked forbidden key: {forbidden}")
    if meta.get("production_executed") is not False:
        bad("audit metadata production_executed must be false")
    if meta.get("note") != "ok":
        bad("audit metadata should keep safe extra keys")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] audit mapping complete; metadata redacts secrets/CoT; production_executed false")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
