"""Step AT-M3.4 -- what migrations 040 and 041 must and must not contain.

Static, so it runs without a database. It asserts the things a reviewer would otherwise have to
take on trust: that the plan's provenance is a real foreign key rather than a convention, that the
two outcomes are paired to the columns they imply, that no Proposal table, Challenge table or
second decision table was invented on the way here, and that widening the AT-M3.1 verb constraint
touched nothing else in AT-M3.1.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FORWARD = ROOT / "migrations" / "040_at_m3_4_planning_decisions.sql"
_DOWN = ROOT / "migrations" / "040_at_m3_4_planning_decisions_down.sql"
_VERB = ROOT / "migrations" / "041_at_m3_4_decompose_plan_verb.sql"
_VERB_DOWN = ROOT / "migrations" / "041_at_m3_4_decompose_plan_verb_down.sql"


def _sql_body(path: Path) -> str:
    """The SQL with comment lines removed, so a prose mention is never read as a declaration."""
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("--")
    )


def test_every_migration_file_exists_and_is_transactional():
    for path in (_FORWARD, _DOWN, _VERB, _VERB_DOWN):
        sql = path.read_text(encoding="utf-8")
        assert sql.count("BEGIN;") == 1 and sql.count("COMMIT;") == 1, path.name


def test_exactly_one_new_table_is_created():
    created = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", _sql_body(_FORWARD))
    assert created == ["planning_decisions"], created


def test_no_proposal_or_challenge_table_is_invented():
    """The architecture's lineage matrix defines neither, so neither gets a table."""
    body = _sql_body(_FORWARD).lower()
    for absent in (
        "proposals",
        "challenges",
        "planning_proposals",
        "planning_challenges",
        "candidate_plans",
        "plan_drafts",
    ):
        assert f"create table if not exists {absent}" not in body, absent


def test_no_second_decision_table_is_created():
    body = _sql_body(_FORWARD).lower()
    for name in re.findall(r"create table if not exists (\w+)", body):
        assert name == "planning_decisions", name
    # And the real decision is the AT-M2 one, referenced rather than replaced.
    assert "REFERENCES team_decisions(decision_id)" in _sql_body(_FORWARD)


def test_no_existing_table_is_altered_by_the_ledger_migration():
    """AT-D14 pre-cleared exactly one alteration of an AT-M2 table, and it is not in this file."""
    body = _sql_body(_FORWARD)
    assert "ALTER TABLE" not in body.upper()
    assert "DROP COLUMN" not in body.upper()


def test_one_decision_per_discussion_is_a_constraint_not_a_convention():
    sql = _sql_body(_FORWARD)
    assert re.search(r"discussion_id\s+UUID NOT NULL UNIQUE", sql), (
        "the exactly-once anchor must be a UNIQUE column"
    )
    assert re.search(r"team_decision_id\s+UUID NOT NULL UNIQUE", sql)
    assert re.search(r"idempotency_key\s+TEXT NOT NULL UNIQUE", sql)
    # UNIQUE, but nullable: a no_change decision names no revision, and repeated NULLs do not
    # collide -- while two decisions can still never claim the same revision.
    assert re.search(r"resulting_plan_revision_id\s+UUID UNIQUE", sql)
    assert not re.search(r"resulting_plan_revision_id\s+UUID NOT NULL", sql)


def test_the_candidate_plan_is_bound_by_a_mandatory_foreign_key():
    """The plan's provenance, and the whole point of the remediation."""
    sql = _sql_body(_FORWARD)
    assert re.search(
        r"candidate_plan_message_id\s+UUID NOT NULL REFERENCES team_messages\(message_id\)", sql
    )
    # Not CASCADE: deleting planning evidence must not delete the decision that cites it.
    candidate_line = next(
        line for line in sql.splitlines() if "candidate_plan_message_id" in line and "REFERENCES" in line
    )
    assert "ON DELETE CASCADE" not in candidate_line


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
    assert "outcome IN ('plan_accepted', 'no_change')" in sql
    # No unreachable state is declared: the input gate admits a converged discussion, the planner
    # produces one candidate, and the plan either differs from what the Goal has or it does not.
    for absent in ("no_selection", "'rejected'", "deferred", "unresolved"):
        assert absent not in sql, absent


def test_the_outcome_and_the_columns_must_agree():
    sql = _sql_body(_FORWARD)
    assert "chk_planning_decisions_outcome_shape" in sql
    assert "outcome = 'plan_accepted' AND resulting_plan_revision_id IS NOT NULL" in sql
    assert "outcome = 'no_change'" in sql
    assert "AND resulting_plan_revision_id IS NULL" in sql


def test_the_self_supersede_rule_lives_on_plan_revisions_not_here():
    """Accepting the current draft in place makes predecessor and resulting the same row."""
    assert "chk_planning_decisions_lineage" not in _sql_body(_FORWARD)
    schema = (ROOT / "migrations" / "038_at_m3_2_goal_plan_revision.sql").read_text(
        encoding="utf-8"
    )
    assert "chk_plan_revisions_no_self_supersede" in schema


def test_a_recorded_decision_is_append_only():
    sql = _sql_body(_FORWARD)
    assert "planning_decisions_enforce_append_only" in sql
    assert "trg_planning_decisions_append_only" in sql
    for column in (
        "discussion_id",
        "candidate_plan_message_id",
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
    """M3.4 records a decision. It decomposes nothing into work and dispatches nothing."""
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


# --- 041: the reasoning verb ------------------------------------------------------------------


def test_the_verb_migration_widens_one_constraint_and_nothing_else():
    body = _sql_body(_VERB)
    assert body.upper().count("ALTER TABLE") == 2  # one DROP CONSTRAINT, one ADD CONSTRAINT
    assert "chk_reasoning_invocations_verb" in body
    assert "'propose', 'critique', 'summarize_decision', 'decompose_plan'" in body
    for forbidden in ("ADD COLUMN", "DROP COLUMN", "CREATE TABLE", "DROP TABLE", "DELETE FROM"):
        assert forbidden not in body.upper(), forbidden
    # It touches AT-M3.1 only. AT-D14's one schema prohibition is on further AT-M2 alteration.
    assert "reasoning_invocations" in body
    for other in ("team_messages", "team_decisions", "plan_revisions", "discussion_sessions"):
        assert other not in body, other


def test_the_canonical_037_migration_is_not_rewritten():
    """037 is merged history; a widened constraint is a new file, never an edit to an applied one."""
    original = (ROOT / "migrations" / "037_at_m3_reasoning_invocations.sql").read_text(
        encoding="utf-8"
    )
    assert "decompose_plan" not in original


def test_the_verb_down_migration_refuses_to_delete_reasoning_evidence():
    body = _sql_body(_VERB_DOWN)
    assert "RAISE EXCEPTION" in body
    assert "DELETE FROM" not in body.upper()
    assert "'propose', 'critique', 'summarize_decision'" in body
