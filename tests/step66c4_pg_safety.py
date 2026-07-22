"""Step 66C.4-BE1-R1 -- fail-closed safety guard for destructive PostgreSQL tests.

The Step 66C.4 PostgreSQL tests begin by executing `DROP TABLE ... CASCADE` so each run starts
from a known schema. The Step 66C.4-BE1-R independent review flagged that those fixtures had no
protection against being pointed at a non-ephemeral database.

This guard is FAIL-CLOSED: every check must pass before a destructive fixture may run. If any
check fails -- including a check that cannot be evaluated -- the DSN is refused and the tests
skip rather than dropping anything. It never "allows on error".

Requirements, all mandatory:
  1. STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 must be set (explicit operator opt-in).
  2. BE1_TEST_DATABASE_URL must be set and parseable.
  3. The database name must match an isolated-test naming convention.
  4. The database name must not be a known shared/production-style name.
  5. The connection must not target a known shared runtime port/service name.

No DSN or credential is stored in this repository; the DSN is supplied by the operator at run
time and points at an isolated ephemeral database.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlsplit

OPT_IN_ENV = "STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS"
DSN_ENV = "BE1_TEST_DATABASE_URL"

# An isolated test database must match one of these shapes.
ALLOWED_DB_NAME_PATTERNS = (
    re.compile(r"^step66c4_[a-z0-9_]+$"),
    re.compile(r"^ephemeral_[a-z0-9_]+$"),
    re.compile(r"^[a-z0-9_]+_test$"),
)

# Names that must never be targeted by a destructive fixture, even if they somehow matched above.
FORBIDDEN_DB_NAMES = frozenset(
    {
        "aiagents",
        "aiagents_prod",
        "aiagents_production",
        "aiagents_staging",
        "aiagents_test",
        "postgres",
        "template0",
        "template1",
        "prod",
        "production",
        "staging",
        "shared",
        "main",
    }
)

# Host names that identify a shared runtime service rather than an ephemeral container.
FORBIDDEN_HOSTNAMES = frozenset({"postgres", "db", "database", "aiagents-test-postgres"})


def destructive_pg_refusal_reason() -> str | None:
    """Return None when destructive PostgreSQL tests are permitted, else the refusal reason."""
    if os.environ.get(OPT_IN_ENV) != "1":
        return f"destructive PostgreSQL tests not opted in (set {OPT_IN_ENV}=1)"

    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        return f"{DSN_ENV} is not set"

    try:
        parts = urlsplit(dsn)
        db_name = (parts.path or "").lstrip("/").strip().lower()
        hostname = (parts.hostname or "").strip().lower()
    except Exception:
        return "DSN could not be parsed; refusing to run a destructive fixture"

    if not db_name:
        return "DSN contains no database name; refusing to run a destructive fixture"
    if db_name in FORBIDDEN_DB_NAMES:
        return f"database name '{db_name}' is a protected/shared name"
    if not any(p.match(db_name) for p in ALLOWED_DB_NAME_PATTERNS):
        return (
            f"database name '{db_name}' does not match an isolated-test naming convention "
            "(step66c4_*, ephemeral_*, *_test)"
        )
    if hostname in FORBIDDEN_HOSTNAMES:
        return f"host '{hostname}' looks like a shared runtime service"

    return None


def destructive_pg_allowed() -> bool:
    return destructive_pg_refusal_reason() is None
