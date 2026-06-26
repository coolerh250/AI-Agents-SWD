#!/usr/bin/env python3
"""Step 57 -- multi-project / work-item schema verifier (migration 024)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "MULTI_PROJECT_SCHEMA_VERIFY"
MIG = ROOT / "migrations" / "024_multi_project_work_item_dispatch.sql"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not MIG.is_file():
        bad("missing migration 024")
        print(f"{MARKER}: FAIL")
        return 1
    sql = MIG.read_text(encoding="utf-8").lower()
    for table in (
        "work_item_dispatches",
        "work_item_events",
        "project_delivery_states",
        "project_members",
        "project_delivery_packages",
    ):
        if f"create table if not exists {table}" not in sql:
            bad(f"missing table: {table}")
    # extends existing tables (no recreate)
    if (
        "create table if not exists projects" in sql
        or "create table if not exists project_work_items" in sql
    ):
        bad("must NOT recreate projects / project_work_items (extend only)")
    for col in ("project_key", "environment_scope", "production_allowed", "registry_status"):
        if f"add column if not exists {col}" not in sql:
            bad(f"projects missing extension column: {col}")
    for col in (
        "production_effect",
        "requires_human_approval",
        "lifecycle_state",
        "delivery_package_id",
    ):
        if f"add column if not exists {col}" not in sql:
            bad(f"project_work_items missing extension column: {col}")
    # safety + indexes
    if "production_effect boolean not null default false" not in sql:
        bad("production_effect must default false")
    for idx in ("idx_wid_project_id", "idx_wid_status", "idx_wid_correlation_id"):
        if idx not in sql:
            bad(f"missing index: {idx}")
    if "uuid_generate_v4()" not in sql:
        bad("must use uuid primary keys")
    if "references projects(id)" not in sql:
        bad("missing foreign keys to projects")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] schema extends projects/work_items + adds dispatch/events/state/members/linkage")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
