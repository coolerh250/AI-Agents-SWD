"""Step 66C.4-BE3-RA-1A/RA-1B -- migration-runner safeguard: locking, provenance, and operational
controls for the isolated migration rehearsal foundation.

This project's migrations (see ``migrations/*.sql``) are applied by executing each file's own
self-contained ``BEGIN; ... COMMIT;`` block against a single connection. RA-1A added a session-level
PostgreSQL advisory lock (``apply_chain_locked``) so two concurrent migrators never race on DDL, and
a deterministic ``schema_fingerprint`` utility for before/after schema comparison.

RA-1B closes four findings from the RA-1R independent review:

  H-1 (aborted-transaction cleanup / lock-release failure): ``apply_chain_locked`` now issues an
      explicit ``ROLLBACK`` BEFORE attempting to unlock, preserves the ORIGINAL migration error even
      if a cleanup step itself fails (never masks it), bounds every cleanup step with a timeout
      (immune to indefinite hangs and cooperative with cancellation via ``asyncio.shield``), and
      closes/discards the connection whenever any cleanup step fails, rather than handing back a
      connection that might still be poisoned or still holding the lock.

  M-1 (schema-fingerprint semantic blind spots): ``schema_fingerprint`` now captures constraints via
      ``pg_get_constraintdef()`` (the full semantic definition, including CHECK expressions, FK
      source/target columns, FK ON DELETE/ON UPDATE/MATCH actions, and deferrability clauses), plus
      explicit deferrable/initially-deferred/validated columns, and indexes via ``pg_indexes.indexdef``
      (already capturing partial-index predicates and index expressions) plus an explicit access
      method column. OID-embedded auto-generated NOT NULL pseudo-constraint names remain excluded
      (nullability is separately captured by ``information_schema.columns.is_nullable``).

  M-2 (no migration ledger / version provenance): a new, additive, runner-owned ledger table
      (``platform_schema_migrations``) records, per apply attempt: version, filename, SHA-256
      checksum, status, runner version, timestamps, and expected/observed schema fingerprints.
      ``apply_chain_with_ledger`` uses the ledger (not just schema introspection) to decide whether a
      migration is already applied, detects a checksum mismatch and fails closed
      (``MigrationChecksumMismatchError``), detects schema that exists with NO ledger record and
      refuses to silently adopt it (``UntrackedSchemaError``), and reconciles an ambiguous prior
      "applying" attempt ONLY when the filename, checksum, and observed schema fingerprint all match
      the recorded expectation -- otherwise it fails closed as "drifted."

  M-3 (unbounded waits / no operational controls): the advisory lock wait is now bounded
      (``pg_try_advisory_lock`` polling against a monotonic deadline, not the blocking
      ``pg_advisory_lock``), a bounded ``statement_timeout``/``lock_timeout``/
      ``idle_in_transaction_session_timeout`` is set before applying and restored after (connection
      discarded if restore itself fails), and a read-only ``plan_chain`` (no DDL, no ledger writes)
      plus an operator-facing CLI (``scripts/run_platform_migrations.py --plan`` / ``--apply``) give a
      dry-run and a clear non-zero exit code on failure, with a structured, secret-free result.

RA-1C closes four further findings from the RA-1R reviewer's focused closure of RA-1B (M-2A, M-2B,
M-3A, M-3B). H-1 and M-1 are unmodified.

  M-2A (an ``applied``/``reconciled_after_ambiguous_commit`` ledger row was never re-checked against
      the ACTUAL schema): every time such a row is encountered again (in both ``plan_chain`` and
      ``apply_chain_with_ledger``), the runner now recomputes the owned-object schema fingerprint and
      requires it to still match the migration's committed canonical manifest -- not just that the
      checksum of the file on disk is unchanged. A table/index/constraint that is missing, altered, or
      wrong-shaped (including one dropped by a raw isolated-rehearsal "down") now fails closed
      (``LedgerSchemaMismatchError`` on apply; ``drift_status == "ledger_schema_mismatch"`` on plan)
      instead of being silently treated as healthy.

  M-2B (ambiguous-commit reconciliation had no trustworthy expected fingerprint): a new, committed,
      per-migration canonical manifest (``shared/sdk/backup_dr/migration_manifests/<version>.json``,
      produced once from a clean isolated PostgreSQL 16 rehearsal, never generated from the database
      currently being checked) supplies the ``expected_fingerprint`` BEFORE any DDL runs -- it is
      recorded on the ledger's ``applying`` row at INSERT time, never learned after the fact from a
      successful apply. Reconciliation of an ambiguous "applying" row now additionally requires a
      non-null expected fingerprint (``ExpectedFingerprintMissingError`` if absent) and manifest
      validation (``MigrationManifestError`` if the manifest is missing, or its filename/checksum/
      PostgreSQL-major-version/format-version does not match) before the observed-vs-expected
      comparison is trusted.

  M-3A (``redact_for_operator`` missed the canonical ``postgresql://`` DSN scheme): redaction no longer
      relies on a single substring marker. It recognizes every connection-string scheme this project
      uses (``postgres``/``postgresql``/``postgresql+asyncpg``/``redis``/``rediss``/``http(s)``), any
      bare ``user:password@host`` userinfo fragment, and key=value credential fields (password/secret/
      token/apikey/dsn), and collapses the ENTIRE message to a fixed, endpoint-free string whenever any
      of these is detected -- a partial in-place substitution could otherwise leave an unanticipated
      fragment (username, host, port, database name, query-string token) exposed.

  M-3B (the CLI's ``asyncpg.connect()`` call sat outside its redacting ``try``): both ``--plan`` and
      ``--apply`` now wrap the connection attempt itself in a protected path that never raises a raw
      traceback -- a connect failure prints exactly one redacted JSON object
      (``result_code: "database_connect_failed"``) to stderr and exits 1, and the CLI never prints to
      both stdout and stderr in the same invocation.

None of this is wired into any shared runtime. Migrations 029-035 are unmodified.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

DEFAULT_LOCK_KEY = "be3-ra1-migration-chain-apply"

DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS = 30.0
MIN_LOCK_WAIT_TIMEOUT_SECONDS = 1.0
MAX_LOCK_WAIT_TIMEOUT_SECONDS = 300.0

DEFAULT_POLL_INTERVAL_SECONDS = 0.2
MIN_POLL_INTERVAL_SECONDS = 0.05
MAX_POLL_INTERVAL_SECONDS = 5.0

DEFAULT_STATEMENT_TIMEOUT_MS = 30_000
MIN_STATEMENT_TIMEOUT_MS = 1_000
MAX_STATEMENT_TIMEOUT_MS = 600_000

CLEANUP_STEP_TIMEOUT_SECONDS = 10.0

RUNNER_VERSION = "ra1c-1"
LEDGER_TABLE = "platform_schema_migrations"

MANIFEST_FORMAT_VERSION = 1
SUPPORTED_POSTGRES_MAJOR_VERSIONS = (16,)
MANIFESTS_DIR = Path(__file__).resolve().parent / "migration_manifests"

# Redaction detectors (M-3A): every connection-string scheme this project uses, a bare
# "user:password@host" userinfo fragment even without a recognized scheme, and key=value credential
# fields. Detection drives a whole-message collapse (see redact_for_operator) rather than a targeted
# substring replacement, so an unanticipated fragment can never slip through a partial substitution.
_SECRET_SCHEME_RE = re.compile(
    r"(postgres(?:ql)?(?:\+asyncpg)?|redis|rediss|https?)://", re.IGNORECASE
)
_SECRET_USERINFO_RE = re.compile(r"[A-Za-z0-9_.+-]+:[^\s@/]*@")
_SECRET_KV_RE = re.compile(r"(?i)\b(password|passwd|secret|token|apikey|api_key|dsn)\b\s*[:=]")


class MigrationConfigError(ValueError):
    """Invalid timeout/lock configuration. Fails closed -- never silently clamped."""


class MigrationLockTimeoutError(Exception):
    """The migration-chain advisory lock could not be acquired within the bounded wait."""


class MigrationChecksumMismatchError(Exception):
    """MIGRATION_CHECKSUM_MISMATCH: the ledger's recorded checksum for an already-applied version
    does not match the migration file currently on disk. Never re-executed or overwritten."""


class UntrackedSchemaError(Exception):
    """UNTRACKED_SCHEMA: a migration's target object(s) already exist with no ledger record. Never
    silently adopted; requires a separate, explicit adoption/reconciliation procedure."""


class SchemaDriftError(Exception):
    """The observed schema does not match what an ambiguous or partially-applied ledger entry
    expects. Fails closed; the chain stops."""


class MigrationManifestError(Exception):
    """MIGRATION_MANIFEST_INVALID: a migration's committed canonical manifest is missing, or its
    filename/checksum/PostgreSQL-major-version/format-version/owned-object list does not match what
    is being checked. Fails closed; never auto-regenerated or overwritten from a live database."""


class LedgerSchemaMismatchError(Exception):
    """LEDGER_SCHEMA_MISMATCH: the ledger records a version as applied/reconciled, but the ACTUAL
    schema no longer matches that migration's canonical manifest fingerprint (a table, index, or
    constraint is missing, altered, or wrong-shaped -- including after a raw isolated-rehearsal
    "down"). Fails closed; never silently treated as healthy and never blindly reapplied."""


class ExpectedFingerprintMissingError(Exception):
    """An ambiguous "applying" ledger row has no recorded expected fingerprint, so it cannot be
    safely reconciled. Fails closed rather than treating a null expectation as an automatic match.
    """


# ---- Migration catalog (runner-owned; does not modify migrations/*.sql) -------------------------

# Tables newly CREATED by each migration -- used for untracked-schema detection (a table that
# already exists here, with no ledger row, means someone/something created it outside this runner).
MIGRATION_CREATED_TABLES: dict[str, tuple[str, ...]] = {
    "031_clarification_lifecycle_outbox_foundation.sql": ("clarification_lifecycle_outbox",),
    "032_be3_resume_replay_authorization.sql": ("resume_replay_authorizations",),
    "033_be3_resume_requests.sql": ("resume_requests",),
    "034_be3_replay_requests.sql": ("replay_requests",),
    "035_be3_production_action_approvals.sql": ("production_action_approvals",),
}

# All tables a migration's fingerprint should cover, including pre-existing tables it only ALTERS
# (031 adds six columns to operator_clarification_requests without creating it).
MIGRATION_FINGERPRINT_TABLES: dict[str, tuple[str, ...]] = {
    "031_clarification_lifecycle_outbox_foundation.sql": (
        "clarification_lifecycle_outbox",
        "operator_clarification_requests",
    ),
    **{
        k: v
        for k, v in MIGRATION_CREATED_TABLES.items()
        if k != "031_clarification_lifecycle_outbox_foundation.sql"
    },
}

_VERSION_RE = re.compile(r"^(\d+)_")


def _migration_version(filename: str) -> str:
    m = _VERSION_RE.match(filename)
    if not m:
        raise ValueError(f"cannot derive a migration version from filename: {filename}")
    return m.group(1)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _looks_secret_shaped(text: str) -> bool:
    if _SECRET_SCHEME_RE.search(text):
        return True
    if _SECRET_USERINFO_RE.search(text):
        return True
    if _SECRET_KV_RE.search(text):
        return True
    return False


def redact_for_operator(text: str) -> str:
    """Never surface a DSN, password, token, or credential-shaped string in an operator-facing
    error or log. Detection covers every connection-string scheme this project uses (postgres/
    postgresql/postgresql+asyncpg/redis/rediss/http(s)), a bare user:password@host userinfo
    fragment, and key=value credential fields -- not a single substring marker. Whenever any of
    these is detected the ENTIRE message is collapsed to a fixed, endpoint-free string (a partial
    in-place substitution could otherwise leave username, host, port, database name, or a
    query-string token exposed). Bounded length so a runaway message can't flood output either."""
    if _looks_secret_shaped(text):
        return "[redacted: message contained secret-shaped content]"
    return text[:500]


def _validate_timeout_config(
    lock_wait_timeout_seconds: float,
    poll_interval_seconds: float,
    statement_timeout_ms: int,
) -> None:
    if not (
        MIN_LOCK_WAIT_TIMEOUT_SECONDS <= lock_wait_timeout_seconds <= MAX_LOCK_WAIT_TIMEOUT_SECONDS
    ):
        raise MigrationConfigError(
            f"lock_wait_timeout_seconds={lock_wait_timeout_seconds} outside "
            f"[{MIN_LOCK_WAIT_TIMEOUT_SECONDS}, {MAX_LOCK_WAIT_TIMEOUT_SECONDS}]"
        )
    if not (MIN_POLL_INTERVAL_SECONDS <= poll_interval_seconds <= MAX_POLL_INTERVAL_SECONDS):
        raise MigrationConfigError(
            f"poll_interval_seconds={poll_interval_seconds} outside "
            f"[{MIN_POLL_INTERVAL_SECONDS}, {MAX_POLL_INTERVAL_SECONDS}]"
        )
    if poll_interval_seconds > lock_wait_timeout_seconds:
        raise MigrationConfigError(
            "poll_interval_seconds must not exceed lock_wait_timeout_seconds"
        )
    if not (MIN_STATEMENT_TIMEOUT_MS <= statement_timeout_ms <= MAX_STATEMENT_TIMEOUT_MS):
        raise MigrationConfigError(
            f"statement_timeout_ms={statement_timeout_ms} outside "
            f"[{MIN_STATEMENT_TIMEOUT_MS}, {MAX_STATEMENT_TIMEOUT_MS}]"
        )


async def _acquire_lock_bounded(
    conn: Any, lock_key: str, timeout_seconds: float, poll_interval_seconds: float
) -> bool:
    """Non-blocking probe (pg_try_advisory_lock), polled against a monotonic deadline -- never the
    blocking pg_advisory_lock, so a crashed/hung holder can never wedge a caller forever."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        got = await conn.fetchval("SELECT pg_try_advisory_lock(hashtextextended($1, 0))", lock_key)
        if got:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(poll_interval_seconds, remaining))


async def _safe_cleanup_step(coro: Any, *, timeout_seconds: float) -> BaseException | None:
    """Run one cleanup step (ROLLBACK, unlock, timeout-restore, ...) shielded from outer
    cancellation and bounded by its own timeout, so cleanup can never hang forever and a
    cancellation of the CALLER cannot abandon a cleanup step half-done. Returns the exception if the
    step failed, else None -- never raises."""
    try:
        await asyncio.wait_for(asyncio.shield(coro), timeout=timeout_seconds)
        return None
    except BaseException as exc:  # noqa: BLE001 -- deliberately catches cancellation too
        return exc


async def apply_migration_file(conn: Any, path: Path) -> None:
    """Execute one migration file's own BEGIN/COMMIT block. Never wrapped in an outer
    ``conn.transaction()`` -- the SQL text manages its own transaction boundary."""
    await conn.execute(path.read_text(encoding="utf-8"))


async def _set_bounded_statement_timeouts(conn: Any, statement_timeout_ms: int) -> dict[str, str]:
    """Set bounded statement/lock/idle-in-transaction timeouts, returning the PRIOR values (as
    returned by SHOW, which are valid literals for a later SET) so they can be restored."""
    saved: dict[str, str] = {}
    for setting in ("statement_timeout", "lock_timeout", "idle_in_transaction_session_timeout"):
        saved[setting] = await conn.fetchval(f"SHOW {setting}")
    ms = int(statement_timeout_ms)
    await conn.execute(f"SET statement_timeout = {ms}")
    await conn.execute(f"SET lock_timeout = {ms}")
    await conn.execute(f"SET idle_in_transaction_session_timeout = {ms}")
    return saved


async def _restore_timeouts(conn: Any, saved: dict[str, str]) -> None:
    for setting, value in saved.items():
        await conn.execute(f"SET {setting} = '{value}'")


async def apply_chain_locked(
    conn: Any,
    migrations_dir: Path,
    filenames: Sequence[str],
    *,
    lock_key: str = DEFAULT_LOCK_KEY,
    lock_wait_timeout_seconds: float = DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> None:
    """Apply ``filenames`` (relative to ``migrations_dir``), in order, on ``conn``, serialized by a
    bounded session-level advisory lock. On ANY failure: explicit ROLLBACK is attempted BEFORE
    unlock (never the reverse); the ORIGINAL migration error is always what propagates (a cleanup
    failure is recorded as ``.ra1b_cleanup_errors`` on that same exception, never raised in its
    place); every cleanup step is bounded and cancellation-safe; the connection is closed/discarded
    if any cleanup step fails, so a poisoned or still-locked connection is never handed back."""
    _validate_timeout_config(
        lock_wait_timeout_seconds, poll_interval_seconds, DEFAULT_STATEMENT_TIMEOUT_MS
    )
    got = await _acquire_lock_bounded(
        conn, lock_key, lock_wait_timeout_seconds, poll_interval_seconds
    )
    if not got:
        raise MigrationLockTimeoutError(
            f"could not acquire the migration-chain advisory lock within {lock_wait_timeout_seconds}s"
        )

    original_error: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    try:
        for name in filenames:
            await apply_migration_file(conn, migrations_dir / name)
    except BaseException as exc:  # noqa: BLE001 -- deliberately catches cancellation too
        original_error = exc
    finally:
        if original_error is not None:
            err = await _safe_cleanup_step(
                conn.execute("ROLLBACK"), timeout_seconds=CLEANUP_STEP_TIMEOUT_SECONDS
            )
            if err is not None:
                cleanup_errors.append(err)
        err = await _safe_cleanup_step(
            conn.fetchval("SELECT pg_advisory_unlock(hashtextextended($1, 0))", lock_key),
            timeout_seconds=CLEANUP_STEP_TIMEOUT_SECONDS,
        )
        if err is not None:
            cleanup_errors.append(err)
        if cleanup_errors:
            with contextlib.suppress(BaseException):
                await conn.close()

    if original_error is not None:
        original_error.ra1b_connection_reusable = not cleanup_errors  # type: ignore[attr-defined]
        original_error.ra1b_cleanup_errors = cleanup_errors  # type: ignore[attr-defined]
        raise original_error


# ---- Schema fingerprint (M-1: semantically complete) ---------------------------------------------

_COLUMNS_QUERY = """
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = $1
ORDER BY column_name
"""

# pg_get_constraintdef() renders the FULL semantic definition -- CHECK expression body, FK source/
# target columns, FK ON DELETE/ON UPDATE/MATCH actions, and any non-default deferrability clause --
# as one canonical, PostgreSQL-generated string. condeferrable/condeferred/convalidated are also
# surfaced explicitly (redundant with the text, but explicit per this stage's own requirement).
_CONSTRAINTS_QUERY = """
SELECT
    con.conname AS constraint_name,
    con.contype AS constraint_type,
    pg_get_constraintdef(con.oid) AS definition,
    con.condeferrable AS deferrable,
    con.condeferred AS initially_deferred,
    con.convalidated AS validated
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
WHERE nsp.nspname = 'public' AND rel.relname = $1
  -- Exclude PostgreSQL's auto-generated per-column NOT NULL pseudo-constraints (named
  -- "<namespace_oid>_<table_oid>_<attnum>_not_null" since PG 12). Their names embed the table's
  -- OID, which changes across a DROP+CREATE, so they are not stable across a down+reapply cycle --
  -- nullability is already fully captured by information_schema.columns.is_nullable below, so
  -- excluding them loses no real semantic coverage.
  AND NOT (con.contype = 'c' AND con.conname ~ '^[0-9]+_[0-9]+_[0-9]+_not_null$')
ORDER BY con.conname
"""

# pg_indexes.indexdef already includes the access method ("USING btree"), any partial-index WHERE
# predicate, and any index expression, as PostgreSQL's own canonical text. am.amname is also
# surfaced explicitly per this stage's own requirement.
_INDEXES_QUERY = """
SELECT
    i.indexname,
    i.indexdef,
    ix.indisunique AS is_unique,
    am.amname AS access_method
FROM pg_indexes i
JOIN pg_namespace n ON n.nspname = i.schemaname
JOIN pg_class ic ON ic.relname = i.indexname AND ic.relnamespace = n.oid
JOIN pg_index ix ON ix.indexrelid = ic.oid
JOIN pg_am am ON am.oid = ic.relam
WHERE i.schemaname = 'public' AND i.tablename = $1
ORDER BY i.indexname
"""


async def schema_fingerprint(conn: Any, table_names: Sequence[str]) -> dict[str, Any]:
    """A deterministic, order-independent snapshot of each table's columns, constraints (via
    pg_get_constraintdef -- CHECK expressions, FK actions/match/deferrability, PK/unique), and
    indexes (via indexdef -- partial predicates, expressions, access method). Two fingerprints
    computed from independently-applied schemas are directly comparable with ``==``; a table that
    does not exist yields an explicit ``None`` marker rather than an error."""
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


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


# ---- Canonical migration manifests (M-2B: golden expected fingerprint) ---------------------------
#
# Each committed manifest (shared/sdk/backup_dr/migration_manifests/<version>.json) is produced ONCE
# from a clean, isolated PostgreSQL 16 rehearsal and committed after review -- never generated from,
# or trusted from, the database currently being checked. It supplies the expected_fingerprint BEFORE
# any DDL runs, so reconciliation of an ambiguous commit never has to "learn" what to expect from a
# possibly-compromised or possibly-drifted live schema.


@dataclasses.dataclass(frozen=True)
class MigrationManifest:
    migration_version: str
    migration_filename: str
    migration_sha256: str
    postgres_major_version: int
    owned_objects: tuple[str, ...]
    canonical_semantic_fingerprint: str
    manifest_format_version: int


def _load_manifest(filename: str) -> MigrationManifest:
    version = _migration_version(filename)
    path = MANIFESTS_DIR / f"{version}.json"
    if not path.is_file():
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_MISSING: no canonical manifest at {path.name}"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_INVALID: {path.name} is not valid JSON"
        ) from exc
    try:
        manifest = MigrationManifest(
            migration_version=str(data["migration_version"]),
            migration_filename=str(data["migration_filename"]),
            migration_sha256=str(data["migration_sha256"]),
            postgres_major_version=int(data["postgres_major_version"]),
            owned_objects=tuple(data["owned_objects"]),
            canonical_semantic_fingerprint=str(data["canonical_semantic_fingerprint"]),
            manifest_format_version=int(data["manifest_format_version"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_INVALID: {path.name} is missing or has an invalid field"
        ) from exc
    if manifest.manifest_format_version != MANIFEST_FORMAT_VERSION:
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_INVALID: {path.name} format version "
            f"{manifest.manifest_format_version} is not recognized (expected "
            f"{MANIFEST_FORMAT_VERSION})"
        )
    if manifest.migration_version != version:
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_INVALID: {path.name} migration_version does not match its filename"
        )
    if manifest.migration_filename != filename:
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_INVALID: {path.name} migration_filename does not match {filename}"
        )
    expected_owned = set(
        MIGRATION_FINGERPRINT_TABLES.get(filename, MIGRATION_CREATED_TABLES.get(filename, ()))
    )
    if expected_owned and set(manifest.owned_objects) != expected_owned:
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_INVALID: {path.name} owned_objects does not match the runner's own "
            f"catalog for {filename}"
        )
    return manifest


async def _validate_manifest(conn: Any, filename: str, checksum: str) -> MigrationManifest:
    """Load AND fully validate a migration's canonical manifest: filename/version/format already
    checked by ``_load_manifest``; here we additionally confirm the manifest's recorded checksum
    matches the migration file actually on disk, and that the connected PostgreSQL major version is
    both supported and matches what the manifest was generated against. Fails closed on any
    mismatch -- never regenerates or overwrites the manifest, never proceeds on a best-effort basis.
    """
    manifest = _load_manifest(filename)
    if manifest.migration_sha256 != checksum:
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_INVALID: {filename}'s on-disk checksum does not match its "
            "committed canonical manifest"
        )
    if manifest.postgres_major_version not in SUPPORTED_POSTGRES_MAJOR_VERSIONS:
        raise MigrationManifestError(
            "MIGRATION_MANIFEST_INVALID: manifest declares an unsupported PostgreSQL major version "
            f"{manifest.postgres_major_version}"
        )
    server_version_num = await conn.fetchval("SHOW server_version_num")
    connected_major = int(server_version_num) // 10000
    if connected_major != manifest.postgres_major_version:
        raise MigrationManifestError(
            f"MIGRATION_MANIFEST_INVALID: connected PostgreSQL major version {connected_major} does "
            f"not match the manifest's {manifest.postgres_major_version}"
        )
    return manifest


# ---- Migration ledger (M-2: version/checksum/status provenance) ----------------------------------

_LEDGER_BOOTSTRAP_SQL = f"""
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} (
    attempt_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    migration_version     TEXT NOT NULL,
    migration_filename    TEXT NOT NULL,
    migration_sha256      TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'applying',
    runner_version        TEXT NOT NULL,
    error_code            TEXT,
    expected_fingerprint  TEXT,
    observed_fingerprint  TEXT,
    started_at            TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    applied_at            TIMESTAMPTZ,
    failed_at             TIMESTAMPTZ,
    resolution            TEXT,
    CONSTRAINT chk_psm_status CHECK (status IN
        ('applying', 'applied', 'failed', 'drifted', 'reconciled_after_ambiguous_commit'))
);
CREATE INDEX IF NOT EXISTS idx_psm_version ON {LEDGER_TABLE} (migration_version);
"""


async def ensure_ledger_bootstrapped(conn: Any) -> None:
    """Additive, idempotent bootstrap of the runner-owned ledger table. Must be called AFTER the
    migration-chain advisory lock is already held, so two concurrent callers never race to create
    it (CREATE TABLE IF NOT EXISTS is safe either way, but serializing avoids a spurious duplicate-
    object warning under real concurrency)."""
    await conn.execute(_LEDGER_BOOTSTRAP_SQL)


async def _insert_applying_row(
    conn: Any,
    version: str,
    filename: str,
    checksum: str,
    runner_version: str,
    expected_fingerprint: str,
) -> str:
    """Insert the 'applying' row WITH its expected_fingerprint already populated from the migration's
    canonical manifest -- M-2B requires this to exist BEFORE the migration SQL runs, never learned
    from the schema after a successful apply."""
    row = await conn.fetchrow(
        f"INSERT INTO {LEDGER_TABLE} "
        "(migration_version, migration_filename, migration_sha256, status, runner_version, "
        "expected_fingerprint) "
        "VALUES ($1, $2, $3, 'applying', $4, $5) RETURNING attempt_id",
        version,
        filename,
        checksum,
        runner_version,
        expected_fingerprint,
    )
    return str(row["attempt_id"])


async def _mark_applied(conn: Any, attempt_id: str, observed_fingerprint_str: str) -> None:
    """Record the observed fingerprint only -- expected_fingerprint was already set (from the
    manifest) at INSERT time and must never be overwritten here."""
    await conn.execute(
        f"UPDATE {LEDGER_TABLE} SET status = 'applied', applied_at = statement_timestamp(), "
        "observed_fingerprint = $2 WHERE attempt_id = $1",
        attempt_id,
        observed_fingerprint_str,
    )


async def _mark_failed(conn: Any, attempt_id: str, error_code: str) -> None:
    await conn.execute(
        f"UPDATE {LEDGER_TABLE} SET status = 'failed', failed_at = statement_timestamp(), "
        "error_code = $2 WHERE attempt_id = $1",
        attempt_id,
        error_code,
    )


async def _mark_drifted(conn: Any, attempt_id: str) -> None:
    await conn.execute(
        f"UPDATE {LEDGER_TABLE} SET status = 'drifted', failed_at = statement_timestamp() "
        "WHERE attempt_id = $1",
        attempt_id,
    )


async def _mark_reconciled(conn: Any, attempt_id: str, observed_fingerprint_str: str) -> None:
    await conn.execute(
        f"UPDATE {LEDGER_TABLE} SET status = 'reconciled_after_ambiguous_commit', "
        "applied_at = statement_timestamp(), observed_fingerprint = $2, "
        "resolution = 'ambiguous_commit_reconciled' WHERE attempt_id = $1",
        attempt_id,
        observed_fingerprint_str,
    )


@dataclasses.dataclass
class MigrationRunResult:
    run_id: str
    mode: str
    started_at: str
    completed_at: str | None
    current_version: str | None
    target_version: str | None
    applied_versions: list[str]
    reconciled_versions: list[str]
    failed_version: str | None
    result_code: str
    lock_wait_duration_seconds: float | None


async def apply_chain_with_ledger(
    conn: Any,
    migrations_dir: Path,
    filenames: Sequence[str],
    *,
    lock_key: str = DEFAULT_LOCK_KEY,
    lock_wait_timeout_seconds: float = DEFAULT_LOCK_WAIT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS,
) -> MigrationRunResult:
    """Ledger-aware, provenance-tracked, bounded-timeout, lock-serialized chain apply. Closes M-2
    and M-3 on top of the H-1-safe locking/cleanup semantics in ``apply_chain_locked``. Never
    modifies migrations/*.sql; the ledger is a separate, runner-owned, additive table."""
    _validate_timeout_config(lock_wait_timeout_seconds, poll_interval_seconds, statement_timeout_ms)
    run_id = str(uuid.uuid4())
    started = _utcnow_iso()

    lock_wait_start = time.monotonic()
    got = await _acquire_lock_bounded(
        conn, lock_key, lock_wait_timeout_seconds, poll_interval_seconds
    )
    lock_wait_duration = time.monotonic() - lock_wait_start
    if not got:
        raise MigrationLockTimeoutError(
            f"could not acquire the migration-chain advisory lock within {lock_wait_timeout_seconds}s"
        )

    applied: list[str] = []
    reconciled: list[str] = []
    failed_version: str | None = None
    result_code = "success"
    original_error: BaseException | None = None
    pending_ledger_update: tuple[str, str] | None = None
    saved_timeouts: dict[str, str] | None = None
    cleanup_errors: list[BaseException] = []
    # M-2A/M-2B structured-result fields (RA-1C), attached to the raised exception on failure.
    ledger_status_out: str | None = None
    expected_fingerprint_out: str | None = None
    observed_fingerprint_out: str | None = None
    diagnostic_code: str | None = None

    try:
        await ensure_ledger_bootstrapped(conn)
        saved_timeouts = await _set_bounded_statement_timeouts(conn, statement_timeout_ms)

        for filename in filenames:
            version = _migration_version(filename)
            checksum = _sha256_file(migrations_dir / filename)
            created_tables = MIGRATION_CREATED_TABLES.get(filename, ())

            existing = await conn.fetchrow(
                f"SELECT * FROM {LEDGER_TABLE} WHERE migration_version = $1 "
                "ORDER BY started_at DESC LIMIT 1",
                version,
            )

            if existing is not None and existing["status"] in (
                "applied",
                "reconciled_after_ambiguous_commit",
            ):
                if existing["migration_sha256"] != checksum:
                    failed_version = version
                    result_code = "checksum_mismatch"
                    ledger_status_out = existing["status"]
                    diagnostic_code = "checksum_mismatch"
                    raise MigrationChecksumMismatchError(
                        f"MIGRATION_CHECKSUM_MISMATCH: {filename} ledger checksum does not match "
                        "the file on disk"
                    )
                # M-2A: an applied/reconciled row is re-verified against the ACTUAL schema every
                # time it is encountered again -- not just that the file's checksum is unchanged.
                # This is the ONLY thing that can detect a table/index/constraint dropped or altered
                # out of band (including by a raw isolated-rehearsal "down").
                manifest = await _validate_manifest(conn, filename, checksum)
                observed_now = _stable_json(
                    await schema_fingerprint(conn, list(manifest.owned_objects))
                )
                if observed_now != manifest.canonical_semantic_fingerprint:
                    failed_version = version
                    result_code = "ledger_schema_mismatch"
                    ledger_status_out = existing["status"]
                    expected_fingerprint_out = manifest.canonical_semantic_fingerprint
                    observed_fingerprint_out = observed_now
                    diagnostic_code = "ledger_schema_mismatch"
                    raise LedgerSchemaMismatchError(
                        f"LEDGER_SCHEMA_MISMATCH: {version}: ledger status={existing['status']} but "
                        "the actual schema no longer matches the canonical manifest fingerprint "
                        "(missing, altered, or wrong-shaped object)"
                    )
                continue  # ledger-authoritative idempotent skip, schema independently reconfirmed

            if existing is not None and existing["status"] == "applying":
                attempt_id = str(existing["attempt_id"])
                if (
                    existing["migration_filename"] != filename
                    or existing["migration_sha256"] != checksum
                ):
                    failed_version = version
                    result_code = "drifted"
                    pending_ledger_update = (attempt_id, "drifted")
                    raise SchemaDriftError(
                        f"{version}: ledger 'applying' row does not match this filename/checksum"
                    )
                # M-2B: reconciliation of an ambiguous prior attempt requires a NON-NULL expected
                # fingerprint (never treat "no expectation recorded" as an automatic match) plus a
                # valid, matching canonical manifest, before the observed-vs-expected comparison is
                # trusted at all.
                if existing["expected_fingerprint"] is None:
                    failed_version = version
                    result_code = "expected_fingerprint_missing"
                    ledger_status_out = existing["status"]
                    diagnostic_code = "expected_fingerprint_missing"
                    pending_ledger_update = (attempt_id, "drifted")
                    raise ExpectedFingerprintMissingError(
                        f"{version}: ledger 'applying' row has no recorded expected fingerprint; "
                        "cannot safely reconcile"
                    )
                manifest = await _validate_manifest(conn, filename, checksum)
                if existing["expected_fingerprint"] != manifest.canonical_semantic_fingerprint:
                    failed_version = version
                    result_code = "drifted"
                    ledger_status_out = existing["status"]
                    expected_fingerprint_out = manifest.canonical_semantic_fingerprint
                    pending_ledger_update = (attempt_id, "drifted")
                    raise SchemaDriftError(
                        f"{version}: ledger's recorded expected fingerprint no longer matches the "
                        "canonical manifest"
                    )
                complete = all(
                    [
                        await conn.fetchval("SELECT to_regclass('public.' || $1) IS NOT NULL", t)
                        for t in created_tables
                    ]
                )
                if not complete:
                    failed_version = version
                    result_code = "drifted"
                    pending_ledger_update = (attempt_id, "drifted")
                    raise SchemaDriftError(
                        f"{version}: ledger shows 'applying' but the target schema is incomplete"
                    )
                observed = _stable_json(
                    await schema_fingerprint(conn, list(manifest.owned_objects))
                )
                if observed != existing["expected_fingerprint"]:
                    failed_version = version
                    result_code = "drifted"
                    ledger_status_out = existing["status"]
                    expected_fingerprint_out = existing["expected_fingerprint"]
                    observed_fingerprint_out = observed
                    pending_ledger_update = (attempt_id, "drifted")
                    raise SchemaDriftError(
                        f"{version}: observed schema does not match the recorded expected fingerprint"
                    )
                await _mark_reconciled(conn, attempt_id, observed)
                reconciled.append(version)
                continue

            if created_tables and any(
                [
                    await conn.fetchval("SELECT to_regclass('public.' || $1) IS NOT NULL", t)
                    for t in created_tables
                ]
            ):
                failed_version = version
                result_code = "untracked_schema"
                raise UntrackedSchemaError(
                    f"UNTRACKED_SCHEMA: {filename}'s target table(s) already exist with no ledger "
                    "record; refusing to auto-adopt -- requires a separate, explicit adoption "
                    "procedure"
                )

            # M-2B apply lifecycle: acquire chain lock (done, outer) -> verify checksum (done above)
            # -> load+validate canonical manifest -> calculate expected fingerprint from the manifest
            # -> insert ledger row WITH that expected_fingerprint -> execute migration SQL ->
            # calculate observed fingerprint -> require observed == expected -> mark applied.
            manifest = await _validate_manifest(conn, filename, checksum)
            expected_fingerprint = manifest.canonical_semantic_fingerprint

            attempt_id = await _insert_applying_row(
                conn, version, filename, checksum, RUNNER_VERSION, expected_fingerprint
            )

            try:
                await apply_migration_file(conn, migrations_dir / filename)
            except BaseException:
                failed_version = version
                result_code = "failed"
                pending_ledger_update = (attempt_id, "failed")
                raise

            observed = _stable_json(await schema_fingerprint(conn, list(manifest.owned_objects)))
            if observed != expected_fingerprint:
                failed_version = version
                result_code = "fingerprint_mismatch"
                expected_fingerprint_out = expected_fingerprint
                observed_fingerprint_out = observed
                diagnostic_code = "fingerprint_mismatch"
                pending_ledger_update = (attempt_id, "drifted")
                raise SchemaDriftError(
                    f"{version}: observed schema after apply does not match the canonical manifest "
                    "fingerprint"
                )
            await _mark_applied(conn, attempt_id, observed)
            applied.append(version)

    except BaseException as exc:  # noqa: BLE001 -- deliberately catches cancellation too
        original_error = exc
    finally:
        if original_error is not None:
            err = await _safe_cleanup_step(
                conn.execute("ROLLBACK"), timeout_seconds=CLEANUP_STEP_TIMEOUT_SECONDS
            )
            if err is not None:
                cleanup_errors.append(err)
            elif pending_ledger_update is not None:
                attempt_id, status = pending_ledger_update
                mark_coro = (
                    _mark_drifted(conn, attempt_id)
                    if status == "drifted"
                    else _mark_failed(conn, attempt_id, redact_for_operator(str(original_error)))
                )
                err2 = await _safe_cleanup_step(
                    mark_coro, timeout_seconds=CLEANUP_STEP_TIMEOUT_SECONDS
                )
                if err2 is not None:
                    cleanup_errors.append(err2)
        if saved_timeouts is not None:
            err = await _safe_cleanup_step(
                _restore_timeouts(conn, saved_timeouts),
                timeout_seconds=CLEANUP_STEP_TIMEOUT_SECONDS,
            )
            if err is not None:
                cleanup_errors.append(err)
        err = await _safe_cleanup_step(
            conn.fetchval("SELECT pg_advisory_unlock(hashtextextended($1, 0))", lock_key),
            timeout_seconds=CLEANUP_STEP_TIMEOUT_SECONDS,
        )
        if err is not None:
            cleanup_errors.append(err)
        if cleanup_errors:
            with contextlib.suppress(BaseException):
                await conn.close()

    completed = _utcnow_iso()
    if original_error is not None:
        original_error.ra1b_connection_reusable = not cleanup_errors  # type: ignore[attr-defined]
        original_error.ra1b_cleanup_errors = cleanup_errors  # type: ignore[attr-defined]
        original_error.ra1b_result_code = result_code  # type: ignore[attr-defined]
        original_error.ra1b_failed_version = failed_version  # type: ignore[attr-defined]
        original_error.ra1c_ledger_status = ledger_status_out  # type: ignore[attr-defined]
        original_error.ra1c_expected_fingerprint = expected_fingerprint_out  # type: ignore[attr-defined]
        original_error.ra1c_observed_fingerprint = observed_fingerprint_out  # type: ignore[attr-defined]
        original_error.ra1c_diagnostic_code = diagnostic_code  # type: ignore[attr-defined]
        raise original_error

    return MigrationRunResult(
        run_id=run_id,
        mode="apply",
        started_at=started,
        completed_at=completed,
        current_version=(applied[-1] if applied else (reconciled[-1] if reconciled else None)),
        target_version=(_migration_version(filenames[-1]) if filenames else None),
        applied_versions=applied,
        reconciled_versions=reconciled,
        failed_version=None,
        result_code=result_code,
        lock_wait_duration_seconds=lock_wait_duration,
    )


def result_to_dict(result: MigrationRunResult) -> dict[str, Any]:
    return dataclasses.asdict(result)


# ---- Read-only plan / dry-run (M-3) ---------------------------------------------------------------


_PLAN_HEALTHY_DRIFT_STATUSES = ("ok", "pending")


@dataclasses.dataclass
class MigrationPlan:
    current_version: str | None
    target_version: str | None
    pending_versions: list[str]
    checksums: dict[str, str]
    schema_state: dict[str, bool]
    drift_status: dict[str, str]
    untracked_versions: list[str]
    lock_required: bool
    expected_operations: list[str]
    result_code: str


async def plan_chain(conn: Any, migrations_dir: Path, filenames: Sequence[str]) -> MigrationPlan:
    """Read-only inspection: NO DDL, NO ledger writes, NO lock held (a plan cannot itself race
    anything, since it changes nothing)."""
    pending: list[str] = []
    checksums: dict[str, str] = {}
    schema_state: dict[str, bool] = {}
    drift_status: dict[str, str] = {}
    untracked: list[str] = []
    ops: list[str] = []
    current_version: str | None = None

    ledger_exists = bool(
        await conn.fetchval("SELECT to_regclass('public.' || $1) IS NOT NULL", LEDGER_TABLE)
    )

    for filename in filenames:
        version = _migration_version(filename)
        checksum = _sha256_file(migrations_dir / filename)
        checksums[version] = checksum
        created_tables = MIGRATION_CREATED_TABLES.get(filename, ())
        exists = bool(created_tables) and all(
            [
                await conn.fetchval("SELECT to_regclass('public.' || $1) IS NOT NULL", t)
                for t in created_tables
            ]
        )
        schema_state[version] = exists

        row = None
        if ledger_exists:
            row = await conn.fetchrow(
                f"SELECT * FROM {LEDGER_TABLE} WHERE migration_version = $1 "
                "ORDER BY started_at DESC LIMIT 1",
                version,
            )

        if row is not None and row["status"] in ("applied", "reconciled_after_ambiguous_commit"):
            if row["migration_sha256"] != checksum:
                drift_status[version] = "checksum_mismatch"
                pending.append(version)
                ops.append(f"{version}: BLOCKED -- checksum mismatch vs ledger")
                continue
            # M-2A: re-verify the ACTUAL schema against the migration's canonical manifest every
            # time, rather than trusting a checksum match alone -- catches a table/index/constraint
            # that was dropped or altered out of band (including a raw isolated-rehearsal "down").
            try:
                manifest = await _validate_manifest(conn, filename, checksum)
            except MigrationManifestError as exc:
                drift_status[version] = "manifest_invalid"
                pending.append(version)
                ops.append(f"{version}: BLOCKED -- {exc}")
                continue
            observed_now = _stable_json(
                await schema_fingerprint(conn, list(manifest.owned_objects))
            )
            if observed_now != manifest.canonical_semantic_fingerprint:
                drift_status[version] = "ledger_schema_mismatch"
                pending.append(version)
                ops.append(
                    f"{version}: BLOCKED -- ledger status={row['status']} but the actual schema no "
                    "longer matches the canonical manifest fingerprint; "
                    "recreate_ephemeral_database_or_use_forward_fix"
                )
                continue
            drift_status[version] = "ok"
            current_version = version
            continue

        if row is not None and row["status"] == "applying":
            drift_status[version] = "ambiguous_commit_pending_reconciliation"
            pending.append(version)
            ops.append(f"{version}: reconcile ambiguous prior attempt, then apply if still needed")
            continue

        if exists:
            drift_status[version] = "untracked"
            untracked.append(version)
            ops.append(f"{version}: BLOCKED -- untracked schema (objects exist, no ledger row)")
            continue

        drift_status[version] = "pending"
        pending.append(version)
        ops.append(f"{version}: apply")

    result_code = "success"
    for version in drift_status:
        if drift_status[version] not in _PLAN_HEALTHY_DRIFT_STATUSES:
            result_code = drift_status[version]
            break

    return MigrationPlan(
        current_version=current_version,
        target_version=(_migration_version(filenames[-1]) if filenames else None),
        pending_versions=pending,
        checksums=checksums,
        schema_state=schema_state,
        drift_status=drift_status,
        untracked_versions=untracked,
        lock_required=bool(pending),
        expected_operations=ops,
        result_code=result_code,
    )


def plan_to_dict(plan: MigrationPlan) -> dict[str, Any]:
    return dataclasses.asdict(plan)
