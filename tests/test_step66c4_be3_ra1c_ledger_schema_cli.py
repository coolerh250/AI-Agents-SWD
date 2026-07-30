"""Step 66C.4-BE3-RA-1C -- ledger/schema consistency and CLI redaction closure tests.

Real-PostgreSQL 16 coverage for the four findings closed by RA-1C (from the RA-1R reviewer's
focused closure of RA-1B):

- M-2A: an applied/reconciled ledger row is re-checked against the ACTUAL schema (not just the
  file checksum) every time it is encountered again, in both plan_chain and apply_chain_with_ledger.
- M-2B: a committed canonical manifest supplies the expected_fingerprint BEFORE any DDL runs;
  ambiguous-commit reconciliation requires a non-null expected fingerprint and a valid manifest.
- M-3A: redact_for_operator recognizes every connection-string scheme this project uses (not just
  a single substring marker) and collapses the whole message rather than a partial substitution.
- M-3B: the CLI's connection attempt itself is wrapped in a protected path -- a connect failure
  never raises a raw traceback and always prints exactly one redacted JSON object.

Gated by the fail-closed destructive-PG guard shared with every other Step 66C.4 PostgreSQL test.
Nothing here touches any shared database, enables any feature gate, or performs any runtime action.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
MANIFESTS_DIR = REPO / "shared" / "sdk" / "backup_dr" / "migration_manifests"
CLI_SCRIPT = REPO / "scripts" / "run_platform_migrations.py"

BASELINE_FILES = (
    "029_operator_task_api_foundation.sql",
    "030_workroom_clarification_foundation.sql",
)
CHAIN_FILES = (
    "031_clarification_lifecycle_outbox_foundation.sql",
    "032_be3_resume_replay_authorization.sql",
    "033_be3_resume_requests.sql",
    "034_be3_replay_requests.sql",
    "035_be3_production_action_approvals.sql",
)

try:
    import asyncpg

    _HAS_ASYNCPG = True
except ImportError:  # pragma: no cover
    _HAS_ASYNCPG = False

_REFUSAL = destructive_pg_refusal_reason()
_DSN = os.environ.get("BE1_TEST_DATABASE_URL")


def _pg_ok() -> bool:
    if _REFUSAL is not None or not (_HAS_ASYNCPG and _DSN):
        return False
    try:

        async def _ping() -> bool:
            c = await asyncpg.connect(dsn=_DSN, timeout=5)
            await c.close()
            return True

        return asyncio.new_event_loop().run_until_complete(_ping())
    except Exception:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_ok(), reason=(_REFUSAL or "isolated ephemeral PostgreSQL 16 not reachable")
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _runner():
    from shared.sdk.backup_dr import migration_runner

    return migration_runner


async def _apply(conn, name: str) -> None:
    await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _drop_all(conn) -> None:
    await conn.execute(
        "DROP TABLE IF EXISTS production_action_approvals, replay_requests, resume_requests, "
        "resume_replay_authorizations, clarification_lifecycle_outbox, "
        "operator_clarification_requests, task_messages, operator_tasks, "
        "platform_schema_migrations CASCADE;"
    )


async def _apply_baseline(conn) -> None:
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    for name in BASELINE_FILES:
        await _apply(conn, name)
    await _runner().ensure_ledger_bootstrapped(conn)


@pytest.fixture
def dsn() -> str:
    assert _DSN is not None
    return _DSN


def _copy_manifests(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for f in MANIFESTS_DIR.glob("*.json"):
        shutil.copy(f, dest / f.name)


# ---------------------------------------------------------------------------------------------
# M-2A: applied/reconciled ledger row re-checked against the ACTUAL schema
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_ledger_applied_but_table_absent_plan_and_apply_fail_closed(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)

            # Raw isolated-rehearsal "down" of 035 -- drops the table the ledger still says applied.
            await conn.execute("DROP TABLE production_action_approvals CASCADE")

            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.drift_status["035"] == "ledger_schema_mismatch"
            assert plan.current_version != "035"
            assert plan.result_code != "success"
            assert "035" in plan.pending_versions

            with pytest.raises(r.LedgerSchemaMismatchError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)

            # No silent recreate: the table is still absent.
            exists = await conn.fetchval(
                "SELECT to_regclass('public.production_action_approvals') IS NOT NULL"
            )
            assert exists is False
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ledger_applied_but_table_wrong_shaped_fails_closed(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)

            await conn.execute(
                "ALTER TABLE production_action_approvals DROP COLUMN IF EXISTS action_type"
            )

            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.drift_status["035"] == "ledger_schema_mismatch"

            with pytest.raises(r.LedgerSchemaMismatchError) as excinfo:
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert excinfo.value.ra1c_diagnostic_code == "ledger_schema_mismatch"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ledger_applied_missing_index_detected_as_drift(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)

            idx = await conn.fetchval(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'production_action_approvals' "
                "AND indexdef NOT LIKE 'CREATE UNIQUE INDEX%' LIMIT 1"
            )
            assert idx is not None
            await conn.execute(f"DROP INDEX {idx}")

            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.drift_status["035"] == "ledger_schema_mismatch"
            with pytest.raises(r.LedgerSchemaMismatchError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ledger_applied_changed_fk_action_detected_as_drift(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)

            await conn.execute(
                "ALTER TABLE clarification_lifecycle_outbox "
                "DROP CONSTRAINT clarification_lifecycle_outbox_task_id_fkey"
            )
            await conn.execute(
                "ALTER TABLE clarification_lifecycle_outbox "
                "ADD CONSTRAINT clarification_lifecycle_outbox_task_id_fkey "
                "FOREIGN KEY (task_id) REFERENCES operator_tasks(id) ON DELETE CASCADE"
            )

            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.drift_status["031"] == "ledger_schema_mismatch"
            with pytest.raises(r.LedgerSchemaMismatchError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ledger_applied_changed_check_expression_detected_as_drift(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)

            await conn.execute(
                "ALTER TABLE clarification_lifecycle_outbox DROP CONSTRAINT "
                "chk_clo_attempts_nonnegative"
            )
            await conn.execute(
                "ALTER TABLE clarification_lifecycle_outbox ADD CONSTRAINT "
                "chk_clo_attempts_nonnegative CHECK (attempts >= -1)"
            )

            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.drift_status["031"] == "ledger_schema_mismatch"
            with pytest.raises(r.LedgerSchemaMismatchError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ledger_reconciled_row_also_reverified_against_schema(dsn: str) -> None:
    """A reconciled_after_ambiguous_commit row is not exempt from the M-2A re-check either."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            for name in CHAIN_FILES[:-1]:
                await r.apply_chain_with_ledger(conn, MIGRATIONS, (name,))

            manifest = await r._validate_manifest(  # noqa: SLF001 -- test-only introspection
                conn, CHAIN_FILES[-1], r._sha256_file(MIGRATIONS / CHAIN_FILES[-1])  # noqa: SLF001
            )
            await _apply(conn, CHAIN_FILES[-1])
            await conn.execute(
                f"INSERT INTO {r.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, "
                "runner_version, expected_fingerprint) "
                "VALUES ('035', $1, $2, 'applying', $3, $4)",
                CHAIN_FILES[-1],
                r._sha256_file(MIGRATIONS / CHAIN_FILES[-1]),  # noqa: SLF001
                r.RUNNER_VERSION,
                manifest.canonical_semantic_fingerprint,
            )
            result = await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert "035" in result.reconciled_versions

            await conn.execute("DROP TABLE production_action_approvals CASCADE")
            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.drift_status["035"] == "ledger_schema_mismatch"
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------------------------
# Raw down policy: ledger/schema mismatch is expected, never silently recreated
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_raw_isolated_down_produces_mismatch_not_silent_success(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)

            for name in reversed(CHAIN_FILES):
                down_name = name.replace(".sql", "_down.sql")
                await _apply(conn, down_name)

            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.result_code != "success"
            assert plan.drift_status["031"] == "ledger_schema_mismatch"

            with pytest.raises(r.LedgerSchemaMismatchError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)

            exists = await conn.fetchval(
                "SELECT to_regclass('public.clarification_lifecycle_outbox') IS NOT NULL"
            )
            assert exists is False
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_destroy_recreate_then_clean_apply_succeeds(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            for name in reversed(CHAIN_FILES):
                await _apply(conn, name.replace(".sql", "_down.sql"))

            # Simulate "destroy ephemeral database/container -> create a fresh database": drop
            # the ledger and baseline too, then rebuild from a clean slate.
            await _drop_all(conn)
            await _apply_baseline(conn)
            result = await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert result.result_code == "success"
            assert result.applied_versions == ["031", "032", "033", "034", "035"]
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------------------------
# Manifest validation: missing/wrong filename/version/checksum/PG-major/fingerprint all fail closed
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_missing_manifest_fails_closed(dsn: str, tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            empty_dir = tmp_path / "empty_manifests"
            empty_dir.mkdir()
            monkeypatch.setattr(r, "MANIFESTS_DIR", empty_dir)
            with pytest.raises(r.MigrationManifestError, match="MISSING"):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_manifest_wrong_filename_fails_closed(dsn: str, tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            bad_dir = tmp_path / "bad_filename_manifests"
            _copy_manifests(bad_dir)
            data = json.loads((bad_dir / "031.json").read_text(encoding="utf-8"))
            data["migration_filename"] = "031_something_else.sql"
            (bad_dir / "031.json").write_text(json.dumps(data), encoding="utf-8")
            monkeypatch.setattr(r, "MANIFESTS_DIR", bad_dir)
            with pytest.raises(r.MigrationManifestError, match="filename"):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_manifest_wrong_version_fails_closed(dsn: str, tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            bad_dir = tmp_path / "bad_version_manifests"
            _copy_manifests(bad_dir)
            data = json.loads((bad_dir / "031.json").read_text(encoding="utf-8"))
            data["migration_version"] = "099"
            (bad_dir / "031.json").write_text(json.dumps(data), encoding="utf-8")
            monkeypatch.setattr(r, "MANIFESTS_DIR", bad_dir)
            with pytest.raises(r.MigrationManifestError, match="version"):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_manifest_wrong_sql_checksum_fails_closed(dsn: str, tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            bad_dir = tmp_path / "bad_checksum_manifests"
            _copy_manifests(bad_dir)
            data = json.loads((bad_dir / "031.json").read_text(encoding="utf-8"))
            data["migration_sha256"] = "0" * 64
            (bad_dir / "031.json").write_text(json.dumps(data), encoding="utf-8")
            monkeypatch.setattr(r, "MANIFESTS_DIR", bad_dir)
            with pytest.raises(r.MigrationManifestError, match="checksum"):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_manifest_wrong_postgres_major_fails_closed(
    dsn: str, tmp_path: Path, monkeypatch
) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            bad_dir = tmp_path / "bad_major_manifests"
            _copy_manifests(bad_dir)
            data = json.loads((bad_dir / "031.json").read_text(encoding="utf-8"))
            data["postgres_major_version"] = 15
            (bad_dir / "031.json").write_text(json.dumps(data), encoding="utf-8")
            monkeypatch.setattr(r, "MANIFESTS_DIR", bad_dir)
            with pytest.raises(r.MigrationManifestError, match="PostgreSQL major version"):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_manifest_wrong_fingerprint_detected_after_apply(
    dsn: str, tmp_path: Path, monkeypatch
) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            bad_dir = tmp_path / "bad_fingerprint_manifests"
            _copy_manifests(bad_dir)
            data = json.loads((bad_dir / "031.json").read_text(encoding="utf-8"))
            data["canonical_semantic_fingerprint"] = "not-the-real-fingerprint"
            (bad_dir / "031.json").write_text(json.dumps(data), encoding="utf-8")
            monkeypatch.setattr(r, "MANIFESTS_DIR", bad_dir)
            with pytest.raises(r.SchemaDriftError, match="fingerprint"):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, (CHAIN_FILES[0],))
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------------------------
# Ambiguous commit reconciliation: requires a non-null, manifest-matching expected fingerprint
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_ambiguous_commit_reconciles_with_exact_expected_fingerprint(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            manifest = await r._validate_manifest(  # noqa: SLF001
                conn, CHAIN_FILES[0], r._sha256_file(MIGRATIONS / CHAIN_FILES[0])  # noqa: SLF001
            )
            await _apply(conn, CHAIN_FILES[0])
            await conn.execute(
                f"INSERT INTO {r.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, "
                "runner_version, expected_fingerprint) "
                "VALUES ('031', $1, $2, 'applying', $3, $4)",
                CHAIN_FILES[0],
                r._sha256_file(MIGRATIONS / CHAIN_FILES[0]),  # noqa: SLF001
                r.RUNNER_VERSION,
                manifest.canonical_semantic_fingerprint,
            )
            result = await r.apply_chain_with_ledger(conn, MIGRATIONS, (CHAIN_FILES[0],))
            assert result.reconciled_versions == ["031"]
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ambiguous_commit_wrong_shaped_table_rejected(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            manifest = await r._validate_manifest(  # noqa: SLF001
                conn, CHAIN_FILES[0], r._sha256_file(MIGRATIONS / CHAIN_FILES[0])  # noqa: SLF001
            )
            await _apply(conn, CHAIN_FILES[0])
            await conn.execute(
                "ALTER TABLE clarification_lifecycle_outbox DROP CONSTRAINT "
                "chk_clo_attempts_nonnegative"
            )
            await conn.execute(
                f"INSERT INTO {r.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, "
                "runner_version, expected_fingerprint) "
                "VALUES ('031', $1, $2, 'applying', $3, $4)",
                CHAIN_FILES[0],
                r._sha256_file(MIGRATIONS / CHAIN_FILES[0]),  # noqa: SLF001
                r.RUNNER_VERSION,
                manifest.canonical_semantic_fingerprint,
            )
            with pytest.raises(r.SchemaDriftError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, (CHAIN_FILES[0],))
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ambiguous_commit_null_expected_fingerprint_rejected(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await _apply(conn, CHAIN_FILES[0])
            await conn.execute(
                f"INSERT INTO {r.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, runner_version) "
                "VALUES ('031', $1, $2, 'applying', $3)",
                CHAIN_FILES[0],
                r._sha256_file(MIGRATIONS / CHAIN_FILES[0]),  # noqa: SLF001
                r.RUNNER_VERSION,
            )
            with pytest.raises(r.ExpectedFingerprintMissingError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, (CHAIN_FILES[0],))
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ambiguous_commit_manifest_checksum_mismatch_rejected(
    dsn: str, tmp_path: Path, monkeypatch
) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            manifest = await r._validate_manifest(  # noqa: SLF001
                conn, CHAIN_FILES[0], r._sha256_file(MIGRATIONS / CHAIN_FILES[0])  # noqa: SLF001
            )
            await _apply(conn, CHAIN_FILES[0])
            await conn.execute(
                f"INSERT INTO {r.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, "
                "runner_version, expected_fingerprint) "
                "VALUES ('031', $1, $2, 'applying', $3, $4)",
                CHAIN_FILES[0],
                r._sha256_file(MIGRATIONS / CHAIN_FILES[0]),  # noqa: SLF001
                r.RUNNER_VERSION,
                manifest.canonical_semantic_fingerprint,
            )

            bad_dir = tmp_path / "bad_checksum_for_reconcile"
            _copy_manifests(bad_dir)
            data = json.loads((bad_dir / "031.json").read_text(encoding="utf-8"))
            data["migration_sha256"] = "f" * 64
            (bad_dir / "031.json").write_text(json.dumps(data), encoding="utf-8")
            monkeypatch.setattr(r, "MANIFESTS_DIR", bad_dir)

            with pytest.raises(r.MigrationManifestError, match="checksum"):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, (CHAIN_FILES[0],))
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------------------------
# M-3A: DSN and secret redaction -- every scheme this project uses, whole-message collapse
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "could not connect to postgres://svc_user:s3cr3t@internal-db.example:5432/appdb",
        "could not connect to postgresql://svc_user:s3cr3t@internal-db.example:5432/appdb",
        "could not connect to postgresql+asyncpg://svc_user:s3cr3t@internal-db.example:5432/appdb",
        "GET https://api.example.com/webhook?token=s3cr3t-token-value failed",
        "redis://:s3cr3t@internal-cache.example:6379/0 unreachable",
        "rediss://svc_user:s3cr3t@internal-cache.example:6380/0 unreachable",
        "connection failed: password=s3cr3t",
        "connection failed: dsn=postgresql://svc_user:s3cr3t@internal-db.example/appdb",
    ],
)
def test_redact_for_operator_covers_every_dsn_scheme_and_credential_field(message: str) -> None:
    r = _runner()
    redacted = r.redact_for_operator(message)
    for forbidden in (
        "s3cr3t",
        "svc_user",
        "internal-db.example",
        "internal-cache.example",
        "appdb",
    ):
        assert forbidden not in redacted
    assert "postgres://" not in redacted
    assert "postgresql://" not in redacted
    assert "redis://" not in redacted
    assert "rediss://" not in redacted


def test_redact_for_operator_leaves_ordinary_messages_intact() -> None:
    r = _runner()
    message = "migration 031 failed: constraint chk_clo_status violated"
    assert r.redact_for_operator(message) == message


# ---------------------------------------------------------------------------------------------
# M-3B: CLI connect failure -- protected path, exit codes, single redacted JSON object
# ---------------------------------------------------------------------------------------------


def _run_cli(args: list[str], dsn: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PLATFORM_MIGRATIONS_DATABASE_URL"] = dsn
    return subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *args],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


_BAD_DSN = "postgresql://baduser:badsecretvalue@127.0.0.1:1/nonexistent_db_ra1c"


def test_cli_plan_with_unreachable_dsn_exits_1_one_json_no_traceback_no_dsn() -> None:
    result = _run_cli(["--plan"], _BAD_DSN)
    assert result.returncode == 1
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["result_code"] == "database_connect_failed"
    assert payload["mode"] == "plan"
    assert payload["success"] is False
    combined = result.stdout + result.stderr
    assert "baduser" not in combined
    assert "badsecretvalue" not in combined
    assert "127.0.0.1:1" not in combined
    assert "Traceback" not in combined


def test_cli_apply_with_unreachable_dsn_exits_1_one_json_no_traceback_no_dsn() -> None:
    result = _run_cli(["--apply"], _BAD_DSN)
    assert result.returncode == 1
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["result_code"] == "database_connect_failed"
    assert payload["mode"] == "apply"
    assert payload["success"] is False
    combined = result.stdout + result.stderr
    assert "baduser" not in combined
    assert "badsecretvalue" not in combined
    assert "Traceback" not in combined


@requires_pg
def test_cli_plan_success_prints_exactly_one_stdout_json_object(dsn: str) -> None:
    async def setup() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
        finally:
            await conn.close()

    _run(setup())
    result = _run_cli(["--plan"], dsn)
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["result_code"] == "success"


# ---------------------------------------------------------------------------------------------
# Regression: RA-1A/RA-1B ledger lifecycle still works end to end with the manifest wired in
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_full_chain_apply_all_manifests_present_and_valid(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            result = await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert result.result_code == "success"
            assert result.applied_versions == ["031", "032", "033", "034", "035"]
            for version, filename in zip(
                ("031", "032", "033", "034", "035"), CHAIN_FILES, strict=True
            ):
                row = await conn.fetchrow(
                    f"SELECT * FROM {r.LEDGER_TABLE} WHERE migration_version = $1", version
                )
                assert row["status"] == "applied"
                assert row["expected_fingerprint"] is not None
                assert row["expected_fingerprint"] == row["observed_fingerprint"]

            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.result_code == "success"
            assert plan.current_version == "035"

            # Duplicate invocation: still healthy, ledger-authoritative, no re-execution.
            result2 = await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert result2.applied_versions == []
            assert result2.result_code == "success"
        finally:
            await conn.close()

    _run(scenario())
