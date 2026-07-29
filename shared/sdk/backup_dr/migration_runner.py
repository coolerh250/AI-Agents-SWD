"""Step 66C.4-BE3-RA-1A -- minimal, additive migration-runner safeguard.

This project's migrations (see ``migrations/*.sql``) are applied by executing each file's own
self-contained ``BEGIN; ... COMMIT;`` block against a single connection -- there is no separate
bookkeeping/ledger table anywhere in the repository; "already applied" is determined by schema
introspection (every migration is idempotent: ``CREATE TABLE IF NOT EXISTS``, ``CREATE INDEX IF NOT
EXISTS``, guarded ``ADD CONSTRAINT``). Before this module, nothing serialized two concurrent
migrators attempting to advance the SAME chain against the SAME database.

``apply_chain_locked`` closes that gap with a session-level PostgreSQL advisory lock
(``pg_advisory_lock``/``pg_advisory_unlock``, keyed by a fixed, deterministic, server-side hash --
never Python's built-in ``hash()``) held for the ENTIRE chain, so a second concurrent migrator
blocks until the first finishes rather than racing on DDL. This module does not modify, reorder, or
wrap any existing migration file's own transaction -- it only serializes *invocations* of the
unmodified files.

``schema_fingerprint`` computes a deterministic, order-independent snapshot of a set of tables'
columns, constraints, and indexes so two schema states (e.g. before/after a down+reapply rehearsal)
can be compared for exact equality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

DEFAULT_LOCK_KEY = "be3-ra1-migration-chain-apply"


async def apply_migration_file(conn: Any, path: Path) -> None:
    """Execute one migration file's own BEGIN/COMMIT block. Never wrapped in an outer
    ``conn.transaction()`` -- the SQL text manages its own transaction boundary."""
    await conn.execute(path.read_text(encoding="utf-8"))


async def apply_chain_locked(
    conn: Any,
    migrations_dir: Path,
    filenames: Sequence[str],
    *,
    lock_key: str = DEFAULT_LOCK_KEY,
) -> None:
    """Apply ``filenames`` (relative to ``migrations_dir``), in order, on ``conn``, serialized by a
    session-level advisory lock so a concurrent caller applying the same chain against the same
    database blocks until this one finishes instead of racing on DDL. The lock is released even if
    a migration fails partway through the chain."""
    await conn.fetchval("SELECT pg_advisory_lock(hashtextextended($1, 0))", lock_key)
    try:
        for name in filenames:
            await apply_migration_file(conn, migrations_dir / name)
    finally:
        await conn.fetchval("SELECT pg_advisory_unlock(hashtextextended($1, 0))", lock_key)


_COLUMNS_QUERY = """
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = $1
ORDER BY column_name
"""

_CONSTRAINTS_QUERY = """
SELECT tc.constraint_name, tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_schema = 'public' AND tc.table_name = $1
  -- Exclude PostgreSQL's auto-generated per-column NOT NULL pseudo-constraints (named
  -- "<namespace_oid>_<table_oid>_<attnum>_not_null" since PG 12). Their names embed the table's
  -- OID, which changes across a DROP+CREATE, so they are not stable across a down+reapply cycle --
  -- and nullability is already fully captured by information_schema.columns.is_nullable, so
  -- including them would be redundant even when stable.
  AND NOT (tc.constraint_type = 'CHECK' AND tc.constraint_name ~ '^[0-9]+_[0-9]+_[0-9]+_not_null$')
ORDER BY tc.constraint_name
"""

_INDEXES_QUERY = """
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = $1
ORDER BY indexname
"""


async def schema_fingerprint(conn: Any, table_names: Sequence[str]) -> dict[str, Any]:
    """A deterministic, order-independent snapshot of each table's columns, constraints, and
    indexes. Two fingerprints computed from independently-applied schemas are directly comparable
    with ``==``; a table that does not exist yields an explicit empty marker rather than an error,
    so a fingerprint can be taken both before and after a migration without special-casing."""
    fingerprint: dict[str, Any] = {}
    for table in sorted(table_names):
        exists = await conn.fetchval("SELECT to_regclass('public.' || $1) IS NOT NULL", table)
        if not exists:
            fingerprint[table] = None
            continue
        columns = [dict(r) for r in await conn.fetch(_COLUMNS_QUERY, table)]
        constraints = [dict(r) for r in await conn.fetch(_CONSTRAINTS_QUERY, table)]
        indexes = [dict(r) for r in await conn.fetch(_INDEXES_QUERY, table)]
        fingerprint[table] = {
            "columns": columns,
            "constraints": constraints,
            "indexes": indexes,
        }
    return fingerprint
