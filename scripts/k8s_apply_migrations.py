#!/usr/bin/env python3
"""Step 51.2C2 -- fixed, shell-free Kubernetes migration entrypoint (wrapper).

Design baseline for the migration Job. The repo applies migrations as a
forward-only ``psql -f migrations/NNN_*.sql`` loop (no applied-migration
tracking table; SQL-level ``IF NOT EXISTS`` idempotency) and there is no
existing advisory-lock wrapper. This module IS that wrapper: it reuses the
repo's established advisory-lock idiom (``pg_advisory_lock(hashtext($1))``,
see shared/sdk/audit_integrity/store.py) to serialise migration runs.

Safety:
  * NO shell, NO arbitrary command/args; the only input is the fixed env var
    ``DATABASE_URL`` (injected via a Secret reference by the Job).
  * Execution is GATED behind ``AIAGENTS_BATCH_EXECUTE=true``. The Step 51.2C2
    baseline keeps it false everywhere, so this entrypoint performs NO database
    work in this stage (it prints a deterministic plan and exits 0).
  * Forward-only: this wrapper NEVER runs ``*_down.sql``. Rollback stays the
    operator-driven catalog (shared/sdk/backup_dr/migration_catalog.py).

This stage validates the wrapper statically; it is NOT executed. Live behaviour
is a deferred cluster-smoke concern.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Fixed advisory-lock name (reuses the repo's pg_advisory_lock idiom).
MIGRATION_LOCK_NAME = "aiagents_schema_migration_v1"
LOCK_TIMEOUT_MS = 60_000
MIGRATIONS_DIR = Path(os.environ.get("AIAGENTS_MIGRATIONS_DIR", "migrations"))


def _ordered_migrations(directory: Path) -> list[Path]:
    """Forward-only, deterministic order; *_down.sql excluded."""
    return sorted(p for p in directory.glob("*.sql") if not p.name.endswith("_down.sql"))


def _execution_enabled() -> bool:
    return str(os.environ.get("AIAGENTS_BATCH_EXECUTE", "false")).strip().lower() == "true"


async def _apply(database_url: str, migrations: list[Path]) -> None:
    import asyncpg  # imported lazily so the static baseline needs no live driver

    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(f"SET statement_timeout = {LOCK_TIMEOUT_MS}")
        # Session-level advisory lock held across every migration -> only one
        # migration run proceeds at a time (no Kubernetes Lease / API needed).
        await conn.execute("SELECT pg_advisory_lock(hashtext($1)::bigint)", MIGRATION_LOCK_NAME)
        try:
            for path in migrations:
                sql = path.read_text(encoding="utf-8")
                await conn.execute(sql)
                print(f"applied {path.name}")
        finally:
            await conn.execute(
                "SELECT pg_advisory_unlock(hashtext($1)::bigint)", MIGRATION_LOCK_NAME
            )
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    migrations = _ordered_migrations(MIGRATIONS_DIR)
    print(f"migration entrypoint: {len(migrations)} forward migration(s) in {MIGRATIONS_DIR}")
    print(f"advisory lock: pg_advisory_lock(hashtext('{MIGRATION_LOCK_NAME}'))")
    if not _execution_enabled():
        print("AIAGENTS_BATCH_EXECUTE != true -> baseline plan only; no database changes")
        return 0
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is required (Secret reference)", file=sys.stderr)
        return 2
    asyncio.run(_apply(database_url, migrations))
    return 0


if __name__ == "__main__":
    sys.exit(main())
