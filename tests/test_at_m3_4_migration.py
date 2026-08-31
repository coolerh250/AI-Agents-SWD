"""Step AT-M3.4 -- what migration 040 must and must not contain.

Static, so it runs without a database. It asserts the two things a reviewer would otherwise have to
take on trust: that the exactly-once anchor is a real constraint rather than a convention, and that
no Proposal table, Challenge table or second decision table was invented on the way here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FORWARD = ROOT / "migrations" / "040_at_m3_4_planning_decisions.sql"
_DOWN = ROOT / "migrations" / "040_at_m3_4_planning_decisions_down.sql"


def _sql_body(path: Path) -> str:
    """The SQL with comment lines removed, so a prose mention is never read as a declaration."""
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("--")
    )


def test_both_migration_files_exist_and_are_transactional():
    for path in (_FORWARD, _DOWN):
        sql = path.read_text(encoding="utf-8")
        assert sql.count("BEGIN;") == 1 and sql.count("COMMIT;") == 1, path.name


def test_exactly_one_new_table_is_created():
    created = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", _sql_body(_FORWARD))
    assert created == ["planning_decisions"], created


def test_no_proposal_or_challenge_table_is_invented():
    """The architecture's lineage matrix defines neither, so neither gets a table."""
    body = _sql_body(_FORWARD).lower()
    for absent in ("proposals", "challenges", "planning_proposals", "planning_challenges"):
        assert f"create table if not exists {absent}" not in body, absent


def test_no_second_decision_table_is_created():
    body = _sql_body(_FORWARD).lower()
    created = re.findall(r"create table if not exists (\w+)", body)
    for name in created:
        assert name == "planning_decisions", name
    # And the real decision is the AT-M2 one, referenced rather than replaced.
    assert "REFERENCES team_decisions(decision_id)" in _sql_body(_FORWARD)


def test_no_existing_table_is_altered():
    """AT-D14 pre-cleared exactly one alteration of an AT-M2 table, and it is not in this file."""
    body = _sql_body(_FORWARD)
    assert "ALTER TABLE" not in body.upper()
    assert "DROP COLUMN" not in body.upper()


def test_one_decision_per_discussion_is_a_constraint_not_a_convention():
    sql = _sql_body(_FORWARD)
    assert re.search(r"discussion_id\s+UUID NOT NULL UNIQUE", sql), (
        "the exactly-once anchor must be a UNIQUE column"
    )
    # And a decision or a revision cannot be claimed twice either.
    assert re.search(r"team_decision_id\s+UUID NOT NULL UNIQUE", sql)
    assert re.search(r"resulting_plan_revision_id\s+UUID NOT NULL UNIQUE", sql)
    assert re.search(r"idempotency_key\s+TEXT NOT NULL UNIQUE", sql)


def test_the_lineage_is_named_by_foreign_key():
    sql = _sql_body(_FORWARD)
    for parent in (
        "projects(id)",
        "goals(goal_id)",
        "discussion_sessions(discussion_id)",
        "team_messages(message_id)",
        "plan_revisions(plan_revision_id)",
        "team_decisions(decision_id)",
    ):
        assert parent in sql, parent


def test_the_outcome_vocabulary_admits_only_what_the_runtime_produces():
    sql = _sql_body(_FORWARD)
    assert "chk_planning_decisions_outcome" in sql
    assert "outcome = 'plan_accepted'" in sql
    # No unreachable state is declared. The input gate admits only converged discussions, so a
    # no-selection outcome has no trigger and is not pretended into the schema.
    assert "no_selection" not in sql
    assert "rejected" not in sql


def test_a_recorded_decision_is_append_only():
    sql = _sql_body(_FORWARD)
    assert "planning_decisions_enforce_append_only" in sql
    assert "trg_planning_decisions_append_only" in sql
    for column in (
        "discussion_id",
        "team_decision_id",
        "resulting_plan_revision_id",
        "predecessor_plan_revision_id",
        "outcome",
    ):
        assert f"NEW.{column}" in sql, column


def test_no_hidden_reasoning_column_can_exist():
    body = _sql_body(_FORWARD).lower()
    for forbidden in (
        "chain_of_thought",
        "hidden_reasoning",
        "scratchpad",
        "raw_prompt",
        "system_prompt",
        "completion",
        "token_trace",
        "credential",
        "api_key",
        "secret",
    ):
        assert forbidden not in body, forbidden


def test_no_m35_or_execution_column_appears():
    """M3.4 records a decision. It decomposes nothing and dispatches nothing."""
    body = _sql_body(_FORWARD).lower()
    for absent in ("work_item", "workitem", "dispatch", "routing", "run_id", "execution"):
        assert absent not in body, absent


def test_no_approval_table_is_referenced():
    """A TeamDecision is not a human Approval, and this schema cannot pretend otherwise."""
    body = _sql_body(_FORWARD).lower()
    for absent in ("approval", "policy_", "task_roles"):
        assert absent not in body, absent


def test_the_down_migration_removes_only_this_slice():
    body = _sql_body(_DOWN)
    assert "DROP TABLE IF EXISTS planning_decisions;" in body
    dropped = re.findall(r"DROP TABLE IF EXISTS (\w+)", body)
    assert dropped == ["planning_decisions"], dropped
    for preserved in ("team_decisions", "plan_revisions", "discussion_sessions", "team_messages"):
        assert f"DROP TABLE IF EXISTS {preserved}" not in body, preserved
