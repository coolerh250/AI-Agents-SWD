"""Step 66C.4-BE3-RA-1FC3 -- INDEPENDENT final M-3B CLI-contract closure battery.

Written by the original RA-1R / RA-1FC / RA-1FC2 reviewer (continuity), NOT the RA-1D implementation
session. Re-derives the single remaining M-3B residual -- the missing-configuration CLI must follow
the same single-JSON error contract as every other failure path -- from scratch by driving the real
``scripts/run_platform_migrations.py`` as a subprocess against a fresh isolated ephemeral PostgreSQL
16. Every test asserts the ACTUAL observed behavior so the suite passes against the code under review
while the review document interprets it.

Does NOT modify the CLI, the runner, the migrations, the manifests, or the RA-1D tests under review.
The missing/malformed/unreachable-DSN tests need no database and always run; the two real-database
regression tests are gated by the shared fail-closed destructive-PG guard.
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
CHAIN_FILES = (
    "031_clarification_lifecycle_outbox_foundation.sql",
    "032_be3_resume_replay_authorization.sql",
    "033_be3_resume_requests.sql",
    "034_be3_replay_requests.sql",
    "035_be3_production_action_approvals.sql",
)

# Fabricated sentinel credential fragments (NOT real): used to prove no endpoint/credential leaks.
_MALFORMED_DSN = "this-is-not-a-valid-dsn-ra1fc3"
_SECRET_USER = "ra1fc3user"
_SECRET_PW = "Ra1fc3SecretValue"
_SECRET_HOST = "internal-endpoint.example"
_SECRET_DB = "private_ai_agents_db"
_UNREACHABLE_DSN = f"postgresql://{_SECRET_USER}:{_SECRET_PW}@127.0.0.1:1/{_SECRET_DB}"
_SENTINELS = (_SECRET_USER, _SECRET_PW, _SECRET_HOST, _SECRET_DB, DSN_ENV)

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


def _cli(args, env_overrides):
    env = dict(os.environ)
    for key, value in env_overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *args],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _exactly_one_json(text: str) -> dict:
    """Parse `text` as EXACTLY one JSON document -- json.loads raises on a plain-text prefix/suffix
    or a second concatenated document, so a green parse proves the single-output contract."""
    return json.loads(text)


async def _seed_baseline(dsn: str) -> None:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute(
            "DROP TABLE IF EXISTS platform_schema_migrations, production_action_approvals, "
            "replay_requests, resume_requests, resume_replay_authorizations, "
            "clarification_lifecycle_outbox, operator_clarification_requests, task_messages, "
            "operator_tasks CASCADE;"
        )
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        for name in BASELINE_FILES:
            await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
    finally:
        await conn.close()


# ==========================================================================================
# Missing configuration: absent / empty / whitespace-only, x --plan / --apply (6 cases)
# ==========================================================================================
@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "\t", "  \t \n "],
    ids=["absent", "empty", "spaces", "tab", "mixedws"],
)
@pytest.mark.parametrize("flag,mode", [("--plan", "plan"), ("--apply", "apply")])
def test_missing_config_single_json_contract(value, flag, mode) -> None:
    p = _cli([flag], {DSN_ENV: value})
    # exit code
    assert p.returncode == 2, f"{mode}/{value!r}: exit {p.returncode}"
    # stdout completely empty
    assert p.stdout == "", f"{mode}/{value!r}: stdout not empty: {p.stdout!r}"
    # no traceback, no plain-text prefix/suffix -> stderr parses as EXACTLY one JSON object
    assert "Traceback" not in p.stderr
    payload = _exactly_one_json(p.stderr)
    # full required JSON shape
    assert payload == {
        "result_code": "missing_configuration",
        "mode": mode,
        "success": False,
        "message": "Required database configuration is missing.",
        "failed_version": None,
    }, f"{mode}/{value!r}: unexpected payload {payload}"
    # boolean false (not truthy/str), null failed_version, stable code
    assert payload["success"] is False
    assert payload["failed_version"] is None
    # endpoint/credential safety: no env-var name/value or sentinel leaks
    for sentinel in _SENTINELS:
        assert sentinel not in p.stderr, f"{mode}/{value!r}: {sentinel} leaked"


# ==========================================================================================
# Classification: malformed / unreachable are database_connect_failed (exit 1), NOT missing (exit 2)
# ==========================================================================================
@pytest.mark.parametrize("flag,mode", [("--plan", "plan"), ("--apply", "apply")])
def test_malformed_dsn_is_connect_failed_not_missing(flag, mode) -> None:
    p = _cli([flag], {DSN_ENV: _MALFORMED_DSN})
    assert p.returncode == 1, f"{mode}: exit {p.returncode} (must be 1, not 2)"
    assert p.stdout == ""
    assert "Traceback" not in p.stderr
    payload = _exactly_one_json(p.stderr)
    assert payload["result_code"] == "database_connect_failed"
    assert payload["result_code"] != "missing_configuration"
    assert payload["mode"] == mode
    assert _MALFORMED_DSN not in p.stderr


@pytest.mark.parametrize("flag,mode", [("--plan", "plan"), ("--apply", "apply")])
def test_unreachable_dsn_is_connect_failed_not_missing(flag, mode) -> None:
    p = _cli([flag], {DSN_ENV: _UNREACHABLE_DSN})
    assert p.returncode == 1, f"{mode}: exit {p.returncode} (must be 1, not 2)"
    assert p.stdout == ""
    assert "Traceback" not in p.stderr
    payload = _exactly_one_json(p.stderr)
    assert payload["result_code"] == "database_connect_failed"
    assert payload["mode"] == mode
    for sentinel in (_SECRET_USER, _SECRET_PW, _SECRET_HOST, _SECRET_DB):
        assert sentinel not in (p.stdout + p.stderr), f"{sentinel} leaked"


# ==========================================================================================
# Third-party logging must not inject a second line into the single-JSON failure output
# ==========================================================================================
@pytest.mark.parametrize("flag,mode", [("--plan", "plan"), ("--apply", "apply")])
def test_debug_logging_does_not_break_missing_config_json(flag, mode) -> None:
    p = _cli(
        [flag],
        {DSN_ENV: None, "PYTHONASYNCIODEBUG": "1", "PYTHONWARNINGS": "default"},
    )
    assert p.returncode == 2
    assert p.stdout == ""
    payload = _exactly_one_json(p.stderr)
    assert payload["result_code"] == "missing_configuration"


def test_debug_logging_does_not_break_connect_failure_json() -> None:
    p = _cli(
        ["--apply"],
        {DSN_ENV: _UNREACHABLE_DSN, "PYTHONASYNCIODEBUG": "1", "PYTHONWARNINGS": "default"},
    )
    assert p.returncode == 1
    assert p.stdout == ""
    payload = _exactly_one_json(p.stderr)
    assert payload["result_code"] == "database_connect_failed"


# ==========================================================================================
# Existing success + drift contracts must still hold (regression)
# ==========================================================================================
@requires_pg
def test_plan_success_exit0_single_stdout_json(dsn: str) -> None:
    asyncio.new_event_loop().run_until_complete(_seed_baseline(dsn))
    p = _cli(["--plan"], {DSN_ENV: dsn})
    assert p.returncode == 0, p.stderr
    assert p.stderr == ""
    payload = _exactly_one_json(p.stdout)
    assert payload["result_code"] == "success"


@requires_pg
def test_apply_success_exit0_single_stdout_json(dsn: str) -> None:
    asyncio.new_event_loop().run_until_complete(_seed_baseline(dsn))
    p = _cli(["--apply"], {DSN_ENV: dsn})
    assert p.returncode == 0, p.stderr
    assert p.stderr == ""
    payload = _exactly_one_json(p.stdout)
    assert payload["result_code"] == "success"
    assert payload["applied_versions"] == ["031", "032", "033", "034", "035"]


@requires_pg
def test_drift_failure_exit1_single_stderr_json_no_secret(dsn: str) -> None:
    """A ledger/schema drift (a raw-dropped owned table after a ledger apply) must surface via the
    same single-JSON stderr contract with exit 1 -- not exit 2, not a traceback, no secret."""

    async def prep() -> None:
        await _seed_baseline(dsn)
        from shared.sdk.backup_dr import migration_runner as mr

        conn = await asyncpg.connect(dsn=dsn)
        try:
            await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            await conn.execute("DROP TABLE resume_requests CASCADE")
        finally:
            await conn.close()

    asyncio.new_event_loop().run_until_complete(prep())
    p = _cli(["--apply"], {DSN_ENV: dsn})
    assert p.returncode == 1, f"exit {p.returncode}: {p.stderr}"
    assert p.stdout == ""
    assert "Traceback" not in p.stderr
    payload = _exactly_one_json(p.stderr)
    assert payload["result_code"] == "ledger_schema_mismatch"
    # the DSN itself must never be echoed
    assert dsn not in p.stderr


# ==========================================================================================
# Test-update integrity (spec section 10): the RA-1D suite really verifies exactly-one-JSON
# ==========================================================================================
def test_s10_ra1d_suite_enforces_exactly_one_json_and_is_not_weakened() -> None:
    src = (REPO / "tests" / "test_step66c4_be3_ra1d_missing_config_json.py").read_text("utf-8")
    for banned in ("@pytest.mark.xfail", "pytest.skip(", "@pytest.mark.skip"):
        assert banned not in src, f"RA-1D suite contains {banned}"
    # exactly-one-JSON is enforced via json.loads on the FULL stderr string (a plain-text prefix or a
    # second document would raise) -- NOT a relaxed "contains-JSON"/substring membership assertion.
    assert "json.loads(result.stderr)" in src
    assert 'result_code" in result.stderr' not in src, "relaxed contains-JSON assertion present"
    # subprocess output is asserted, not ignored
    assert "result.returncode == 2" in src
    assert 'result.stdout == ""' in src
    # missing / empty / whitespace all covered, both modes
    for token in ("missing_env", "empty_env", "whitespace_only_env"):
        assert token in src
    assert '"--plan", "plan"' in src and '"--apply", "apply"' in src
