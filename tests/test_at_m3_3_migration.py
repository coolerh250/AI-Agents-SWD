"""Step AT-M3.3 -- static assertions against migration 039's SQL text.

Mirrors the assertion style ``test_at_m3_1_migration.py`` uses against 037: parse the file text
rather than require a live database, so these checks run everywhere. The live up/down/reapply
behaviour is exercised separately against real PostgreSQL.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FORWARD = ROOT / "migrations" / "039_at_m3_3_bounded_team_discussion.sql"
_DOWN = ROOT / "migrations" / "039_at_m3_3_bounded_team_discussion_down.sql"


def _sql_body(path: Path) -> str:
    """The migration's executable SQL, with ``--`` comment lines removed.

    The header explains at length what the schema deliberately does NOT store -- prompts, token
    traces, credentials, dispatch -- so a scan for those words has to look at the statements, not
    at the prose describing their absence.
    """
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    )


AT_M2_TABLES = (
    "actor_principals",
    "agent_profiles",
    "project_team_memberships",
    "conversation_threads",
    "team_messages",
    "team_decisions",
    "agent_handoffs",
    "agent_routing_decisions",
)


def test_the_migration_is_additive_and_alters_no_existing_table():
    sql = _FORWARD.read_text(encoding="utf-8")
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql))
    assert created == {"discussion_sessions", "discussion_participants", "discussion_turns"}
    # AT-D14 pre-cleared exactly ONE alteration of an AT-M2 table -- the team_decisions FK AT-M3.2
    # already made -- and "authorizes no other alteration of an AT-M2 table".
    assert "ALTER TABLE" not in sql.upper()


def test_no_existing_message_or_thread_table_is_replaced():
    sql = _FORWARD.read_text(encoding="utf-8")
    for table in AT_M2_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table}" not in sql
    # The discussion reuses the collaboration substrate by foreign key rather than rebuilding it.
    assert "REFERENCES conversation_threads(thread_id)" in sql
    assert "REFERENCES team_messages(message_id)" in sql
    assert "REFERENCES actor_principals(principal_id)" in sql
    assert "REFERENCES reasoning_invocations(invocation_id)" in sql
    assert "REFERENCES goals(goal_id)" in sql
    assert "REFERENCES plan_revisions(plan_revision_id)" in sql


def test_the_forward_migration_drops_no_table():
    sql = _FORWARD.read_text(encoding="utf-8")
    assert "DROP TABLE" not in sql.upper()
    # It may drop and recreate its OWN triggers/functions for idempotency, and nothing else.
    for match in re.findall(r"DROP (\w+) IF EXISTS ([\w.]+)", sql):
        assert match[0] in ("TRIGGER", "FUNCTION")
        assert match[1].startswith("trg_discussion") or match[1].startswith("discussion_")


def test_the_migration_is_reversible():
    sql = _FORWARD.read_text(encoding="utf-8")
    down = _DOWN.read_text(encoding="utf-8")
    for table in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql):
        assert f"DROP TABLE IF EXISTS {table}" in down, table
    for function in re.findall(r"CREATE OR REPLACE FUNCTION (\w+)\(\)", sql):
        assert f"DROP FUNCTION IF EXISTS {function}()" in down, function
    # A down migration that removed a thread or a message would delete collaboration evidence the
    # discussion only scheduled; it must not.
    for table in AT_M2_TABLES:
        assert f"DROP TABLE IF EXISTS {table}" not in down


def test_the_migration_is_idempotent_by_construction():
    sql = _FORWARD.read_text(encoding="utf-8")
    creates = re.findall(r"CREATE (TABLE|INDEX|UNIQUE INDEX) (?!IF NOT EXISTS)", sql)
    assert not creates, creates
    assert sql.strip().startswith("--")
    assert "BEGIN;" in sql and sql.strip().endswith("COMMIT;")


def test_no_column_can_hold_hidden_reasoning():
    """AT-D03 R8 / INV-04, restated by AT-D14 section 4 for every M3 slice."""
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
        "secret",
        "credential",
        "api_key",
        "context",
    )
    for column in columns:
        assert not any(marker in column for marker in forbidden), column


def test_state_and_stop_reason_are_separate_columns():
    sql = _FORWARD.read_text(encoding="utf-8")
    assert re.search(r"^\s+state\s+TEXT NOT NULL DEFAULT 'open'", sql, re.M)
    assert re.search(r"^\s+stop_reason\s+TEXT,\s*$", sql, re.M), "stop_reason must be nullable"
    # Open iff no reason: a terminal row always says why it stopped.
    assert "(state = 'open') = (stop_reason IS NULL)" in sql


def test_exhaustion_can_never_be_recorded_as_convergence():
    sql = _FORWARD.read_text(encoding="utf-8")
    constraint = re.search(
        r"CONSTRAINT chk_discussion_sessions_reason_matches_state CHECK \((.*?)\n    \),",
        sql,
        re.S,
    )
    assert constraint, "the state/reason pairing constraint is missing"
    body = constraint.group(1)
    assert "state = 'converged' AND stop_reason = 'convergence_reached'" in body
    assert "'round_limit_reached'" in body and "state = 'exhausted'" in body
    # And a result for M3.4 only exists on a genuinely converged discussion.
    assert "result_message_id IS NULL OR state = 'converged'" in sql


def test_the_turn_slot_is_unique_which_is_what_makes_one_reply_canonical():
    sql = _FORWARD.read_text(encoding="utf-8")
    assert "UNIQUE (discussion_id, round_index, seat_index)" in sql
    assert "uq_discussion_turns_correlation UNIQUE (correlation_id)" in sql


def test_a_participant_cannot_be_seated_twice():
    sql = _FORWARD.read_text(encoding="utf-8")
    assert "UNIQUE (discussion_id, principal_id)" in sql
    assert "UNIQUE (discussion_id, seat_index)" in sql


def test_one_discussion_per_thread():
    sql = _FORWARD.read_text(encoding="utf-8")
    assert re.search(r"thread_id\s+UUID NOT NULL UNIQUE REFERENCES conversation_threads", sql)


def test_a_duplicate_start_is_unrepresentable():
    sql = _FORWARD.read_text(encoding="utf-8")
    assert re.search(r"idempotency_key\s+TEXT NOT NULL UNIQUE", sql)


def test_bounds_are_required_columns_not_optional_hints():
    sql = _FORWARD.read_text(encoding="utf-8")
    for bound in (
        "max_rounds",
        "max_messages",
        "max_invocations",
        "max_turns_per_participant",
    ):
        assert re.search(rf"^\s+{bound}\s+INT NOT NULL,", sql, re.M), bound
    assert "chk_discussion_sessions_bounds" in sql


def test_no_m34_or_m35_column_appears():
    """M3.3 discusses. It does not decide, decompose or dispatch."""
    sql = _sql_body(_FORWARD).lower()
    for absent in (
        "decision_id",
        "resulting_plan_revision_id",
        "work_item",
        "dispatch",
        "assignment",
        "approval",
        "production_executed",
    ):
        assert absent not in sql, absent


def test_no_production_or_external_surface():
    sql = _sql_body(_FORWARD).lower()
    for absent in ("http", "api_key", "token", "anthropic", "openai", "endpoint"):
        assert absent not in sql, absent
