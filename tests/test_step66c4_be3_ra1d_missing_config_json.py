"""Step 66C.4-BE3-RA-1D -- missing-configuration single-JSON contract closure tests.

Closes the one M-3B residual from the Step 66C.4-BE3-RA-1FC2 second focused closure: a missing,
empty, or whitespace-only ``PLATFORM_MIGRATIONS_DATABASE_URL`` used to print a plain-text line to
stderr before exiting 2, instead of the same single redacted JSON object every other CLI failure
path already used.

Gated by the fail-closed destructive-PG guard shared with every other Step 66C.4 PostgreSQL test
for the two real-database regression tests (success paths); the missing-config/malformed-DSN/
unreachable-DSN tests need no database at all and always run.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
CLI_SCRIPT = REPO / "scripts" / "run_platform_migrations.py"
DSN_ENV = "PLATFORM_MIGRATIONS_DATABASE_URL"

BASELINE_FILES = (
    "029_operator_task_api_foundation.sql",
    "030_workroom_clarification_foundation.sql",
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


@pytest.fixture
def dsn() -> str:
    assert _DSN is not None
    return _DSN


def _run_cli(args: list[str], env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess:
    """env_overrides: a value of None deletes the key from the inherited environment (simulating
    "not set at all"); any other value sets it verbatim (including "" or whitespace-only)."""
    env = dict(os.environ)
    for key, value in env_overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *args],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _assert_missing_configuration_contract(result: subprocess.CompletedProcess, mode: str) -> None:
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stderr)  # raises if stderr is not EXACTLY one JSON object
    assert payload["result_code"] == "missing_configuration"
    assert payload["mode"] == mode
    assert payload["success"] is False
    assert DSN_ENV not in json.dumps(payload)


# ---------------------------------------------------------------------------------------------
# Mandatory: missing / empty / whitespace-only configuration
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode_flag,mode_name", [("--plan", "plan"), ("--apply", "apply")])
def test_cli_missing_env_exits_2_one_json(mode_flag: str, mode_name: str) -> None:
    result = _run_cli([mode_flag], {DSN_ENV: None})
    _assert_missing_configuration_contract(result, mode_name)


@pytest.mark.parametrize("mode_flag,mode_name", [("--plan", "plan"), ("--apply", "apply")])
def test_cli_empty_env_exits_2_one_json(mode_flag: str, mode_name: str) -> None:
    result = _run_cli([mode_flag], {DSN_ENV: ""})
    _assert_missing_configuration_contract(result, mode_name)


@pytest.mark.parametrize("mode_flag,mode_name", [("--plan", "plan"), ("--apply", "apply")])
def test_cli_whitespace_only_env_exits_2_one_json(mode_flag: str, mode_name: str) -> None:
    result = _run_cli([mode_flag], {DSN_ENV: "   \t  "})
    _assert_missing_configuration_contract(result, mode_name)


# ---------------------------------------------------------------------------------------------
# Existing contracts must be preserved: malformed/unreachable DSN still exit 1, never 2
# ---------------------------------------------------------------------------------------------

_MALFORMED_DSN = "this-is-not-a-valid-dsn-at-all"
_UNREACHABLE_DSN = "postgresql://baduser:badsecretvalue@127.0.0.1:1/nonexistent_db_ra1d"


@pytest.mark.parametrize("mode_flag,mode_name", [("--plan", "plan"), ("--apply", "apply")])
def test_cli_malformed_dsn_still_exits_1_not_2(mode_flag: str, mode_name: str) -> None:
    result = _run_cli([mode_flag], {DSN_ENV: _MALFORMED_DSN})
    assert result.returncode == 1
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["result_code"] == "database_connect_failed"
    assert payload["mode"] == mode_name
    assert "Traceback" not in result.stderr
    assert _MALFORMED_DSN not in result.stderr


@pytest.mark.parametrize("mode_flag,mode_name", [("--plan", "plan"), ("--apply", "apply")])
def test_cli_unreachable_dsn_still_exits_1_not_2(mode_flag: str, mode_name: str) -> None:
    result = _run_cli([mode_flag], {DSN_ENV: _UNREACHABLE_DSN})
    assert result.returncode == 1
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["result_code"] == "database_connect_failed"
    assert payload["mode"] == mode_name
    combined = result.stdout + result.stderr
    assert "baduser" not in combined
    assert "badsecretvalue" not in combined
    assert "Traceback" not in combined


# ---------------------------------------------------------------------------------------------
# Existing contracts must be preserved: success paths remain exit 0, single stdout JSON
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_cli_plan_success_still_exits_0_one_stdout_json(dsn: str) -> None:
    async def setup() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await conn.execute(
                "DROP TABLE IF EXISTS production_action_approvals, replay_requests, "
                "resume_requests, resume_replay_authorizations, clarification_lifecycle_outbox, "
                "operator_clarification_requests, task_messages, operator_tasks, "
                "platform_schema_migrations CASCADE;"
            )
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            for name in BASELINE_FILES:
                await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
        finally:
            await conn.close()

    asyncio.new_event_loop().run_until_complete(setup())
    result = _run_cli(["--plan"], {DSN_ENV: dsn})
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["result_code"] == "success"


@requires_pg
def test_cli_apply_success_still_exits_0_one_stdout_json(dsn: str) -> None:
    async def setup() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await conn.execute(
                "DROP TABLE IF EXISTS production_action_approvals, replay_requests, "
                "resume_requests, resume_replay_authorizations, clarification_lifecycle_outbox, "
                "operator_clarification_requests, task_messages, operator_tasks, "
                "platform_schema_migrations CASCADE;"
            )
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            for name in BASELINE_FILES:
                await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
        finally:
            await conn.close()

    asyncio.new_event_loop().run_until_complete(setup())
    result = _run_cli(["--apply"], {DSN_ENV: dsn})
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["result_code"] == "success"
    assert payload["applied_versions"] == ["031", "032", "033", "034", "035"]
