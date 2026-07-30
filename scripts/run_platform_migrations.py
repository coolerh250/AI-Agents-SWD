#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-1B -- operator-facing migration plan/apply CLI (M-3).

Wraps ``shared.sdk.backup_dr.migration_runner``'s ledger-aware, bounded-timeout,
lock-serialized chain apply for migrations 031-035 with an explicit two-mode operator
entry point:

    python scripts/run_platform_migrations.py --plan     # read-only: no DDL, no ledger write
    python scripts/run_platform_migrations.py --apply     # ledger-aware, lock-serialized apply

Requires ``PLATFORM_MIGRATIONS_DATABASE_URL`` (never hardcoded, never logged). Exit code is 0 only
on unambiguous success; any validation/drift/config/migration failure exits non-zero. Output is a
single structured JSON object on stdout (plan/success) or stderr (apply failure); every error is
passed through ``redact_for_operator`` so a DSN, password, or credential-shaped string is never
printed.

This script does NOT apply to any shared database by default -- it is an operator tool, not
wired into any deployment, CI job, or shared runtime. Running it against a real database is a
separate, explicit operator action.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.getcwd())

from shared.sdk.backup_dr import migration_runner as runner  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations"

RA1_CHAIN: tuple[str, ...] = (
    "031_clarification_lifecycle_outbox_foundation.sql",
    "032_be3_resume_replay_authorization.sql",
    "033_be3_resume_requests.sql",
    "034_be3_replay_requests.sql",
    "035_be3_production_action_approvals.sql",
)

DSN_ENV = "PLATFORM_MIGRATIONS_DATABASE_URL"


def _dsn_from_env() -> str:
    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        print(f"{DSN_ENV} is not set; refusing to run.", file=sys.stderr)
        sys.exit(2)
    return dsn


def _print_connect_failure(mode: str) -> int:
    """M-3B: a connection failure must never raise a raw traceback -- it prints exactly one
    redacted JSON object to stderr and exits 1. The underlying exception text is deliberately NOT
    included (asyncpg/libpq connect errors routinely echo the DSN, host, port, and database name
    verbatim), so this never depends on redact_for_operator catching every possible phrasing."""
    payload = {
        "result_code": "database_connect_failed",
        "mode": mode,
        "success": False,
        "message": "Database connection failed.",
        "failed_version": None,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 1


async def _connect_or_none(dsn: str) -> Any:
    import asyncpg

    try:
        return await asyncpg.connect(dsn=dsn)
    except BaseException:  # noqa: BLE001 -- deliberately reports any failure, never a raw traceback
        return None


async def _run_plan(dsn: str) -> int:
    conn = await _connect_or_none(dsn)
    if conn is None:
        return _print_connect_failure("plan")
    try:
        plan = await runner.plan_chain(conn, MIGRATIONS_DIR, RA1_CHAIN)
    finally:
        await conn.close()
    payload = runner.plan_to_dict(plan)
    if plan.result_code != "success":
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


async def _run_apply(dsn: str) -> int:
    conn = await _connect_or_none(dsn)
    if conn is None:
        return _print_connect_failure("apply")
    try:
        try:
            result = await runner.apply_chain_with_ledger(conn, MIGRATIONS_DIR, RA1_CHAIN)
        except BaseException as exc:  # noqa: BLE001 -- deliberately reports any failure, redacted
            payload = {
                "result_code": getattr(exc, "ra1b_result_code", "failed"),
                "mode": "apply",
                "success": False,
                "migration_version": getattr(exc, "ra1b_failed_version", None),
                "failed_version": getattr(exc, "ra1b_failed_version", None),
                "ledger_status": getattr(exc, "ra1c_ledger_status", None),
                "expected_fingerprint": getattr(exc, "ra1c_expected_fingerprint", None),
                "observed_fingerprint": getattr(exc, "ra1c_observed_fingerprint", None),
                "diagnostic_code": getattr(exc, "ra1c_diagnostic_code", None),
                "connection_reusable": getattr(exc, "ra1b_connection_reusable", None),
                "error": runner.redact_for_operator(str(exc)),
            }
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
            return 1
    finally:
        await conn.close()
    print(json.dumps(runner.result_to_dict(result), indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "RA-1 platform migration plan/apply (operator-facing; not wired into any shared "
            "runtime or deployment)."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--plan",
        action="store_true",
        help="Read-only: report current/target version, pending migrations, and drift. No DDL, no ledger writes.",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="Apply the pending chain under the ledger-aware, bounded-timeout, lock-serialized runner.",
    )
    args = parser.parse_args()
    dsn = _dsn_from_env()
    if args.plan:
        return asyncio.run(_run_plan(dsn))
    return asyncio.run(_run_apply(dsn))


if __name__ == "__main__":
    sys.exit(main())
