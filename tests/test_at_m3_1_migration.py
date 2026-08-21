"""Step AT-M3.1 -- static assertions against migration 037's SQL text.

Mirrors the assertion style ``test_at_m2_team_core.py`` uses against migration 036: parse the file
text rather than require a live database, so these checks run everywhere.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FORWARD = ROOT / "migrations" / "037_at_m3_reasoning_invocations.sql"
_DOWN = ROOT / "migrations" / "037_at_m3_reasoning_invocations_down.sql"


def test_the_migration_creates_exactly_one_new_table_and_alters_nothing():
    sql = _FORWARD.read_text(encoding="utf-8")
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql))
    assert created == {"reasoning_invocations"}
    assert "ALTER TABLE" not in sql.upper(), "AT-M3.1 must not modify an existing table"
    assert re.search(r"\bDROP\b", sql.upper()) is None, "the forward migration drops nothing"


def test_the_migration_is_reversible():
    down = _DOWN.read_text(encoding="utf-8")
    sql = _FORWARD.read_text(encoding="utf-8")
    for table in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql):
        assert f"DROP TABLE IF EXISTS {table}" in down, table


def test_the_migration_stores_no_prompt_completion_or_hidden_reasoning_field():
    """AT-D03 R8 / INV-04, restated for AT-M3: metadata only, never the content."""
    sql = _FORWARD.read_text(encoding="utf-8")
    columns = re.findall(
        r"^\s{4,}([a-z_]+)\s+(?:UUID|TEXT|JSONB|BOOLEAN|TIMESTAMPTZ|INT|NUMERIC)", sql, re.M
    )
    assert columns, "no columns parsed -- the check would be vacuous"
    forbidden = (
        "prompt",
        "completion",
        "chain_of_thought",
        "raw_reasoning",
        "hidden_reasoning",
        "reasoning_token",
        "token_trace",
        "scratchpad",
        "system_prompt",
        "unredacted",
        "secret",
        "credential",
        "api_key",
        "password",
    )
    leaks = [c for c in columns if any(marker in c for marker in forbidden)]
    assert leaks == [], f"AT-M3.1 contracted a hidden-reasoning or secret column: {leaks}"


def test_provider_mode_is_constrained_to_the_two_implemented_classes():
    """No live external mode is authorized by this slice -- the CHECK constraint is the proof."""
    sql = _FORWARD.read_text(encoding="utf-8")
    match = re.search(r"chk_reasoning_invocations_provider_mode CHECK \(provider_mode IN \((.*?)\)\)", sql, re.S)
    assert match, "provider_mode CHECK constraint not found"
    modes = set(re.findall(r"'([a-z_]+)'", match.group(1)))
    assert modes == {"mock", "disabled"}


def test_correlation_id_is_unique_not_merely_indexed():
    """The idempotency guarantee lives in the schema, not only in Python."""
    sql = _FORWARD.read_text(encoding="utf-8")
    assert "CONSTRAINT uq_reasoning_invocations_correlation UNIQUE (correlation_id)" in sql


def test_no_column_is_marked_production_executed():
    sql = _FORWARD.read_text(encoding="utf-8")
    columns = re.findall(
        r"^\s{4,}([a-z_]+)\s+(?:UUID|TEXT|JSONB|BOOLEAN|TIMESTAMPTZ|INT|NUMERIC)", sql, re.M
    )
    assert [c for c in columns if "production" in c] == []


def test_forward_references_to_unimplemented_entities_are_absent():
    """Goal and PlanRevision do not exist yet (AT-M3.2+). This table names neither."""
    sql = _FORWARD.read_text(encoding="utf-8")
    assert "goal_id" not in sql.lower()
    assert "plan_revision" not in sql.lower()
