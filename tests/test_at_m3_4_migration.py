"""Step AT-M3.4 (rebaselined) -- what migrations 040 and 041 must and must not contain.

Static, so it runs without a database. It asserts the things a reviewer would otherwise have to
take on trust: that a successful reasoning invocation cannot exist without its artifact, that a
terminal one cannot be edited, that the plan's provenance is a real foreign key rather than a
convention, that the two outcomes are paired to the columns they imply, and that no Proposal
table, Challenge table or second decision table was invented on the way here.

Numbering is derived from canonical main, which ends at 039. 040 is the AT-M3.1 durability
migration this slice depends on; 041 is the AT-M3.4 ledger. The failed lineage numbered them the
other way round, and inheriting its numbers would have meant inheriting a base it no longer has.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_DURABLE = ROOT / "migrations" / "040_at_m3_4_durable_reasoning_artifact.sql"
_DURABLE_DOWN = ROOT / "migrations" / "040_at_m3_4_durable_reasoning_artifact_down.sql"
_FORWARD = ROOT / "migrations" / "041_at_m3_4_planning_decisions.sql"
_DOWN = ROOT / "migrations" / "041_at_m3_4_planning_decisions_down.sql"


def _sql_body(path: Path) -> str:
    """The SQL with prose removed, so a mention is never read as a declaration.

    Both kinds of prose: leading ``--`` comments, and ``COMMENT ON`` statements, whose payload is
    documentation that happens to live inside the SQL. A prohibition sentence naming the thing it
    prohibits must not read as that thing being declared.
    """
    kept: list[str] = []
    inside_comment_on = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if inside_comment_on:
            inside_comment_on = not stripped.endswith(";")
            continue
        if stripped.startswith("--"):
            continue
        if stripped.upper().startswith("COMMENT ON"):
            inside_comment_on = not stripped.endswith(";")
            continue
        kept.append(line)
    return "\n".join(kept)


def test_every_migration_file_exists_and_is_transactional():
    for path in (_DURABLE, _DURABLE_DOWN, _FORWARD, _DOWN):
        sql = path.read_text(encoding="utf-8")
        assert sql.count("BEGIN;") == 1 and sql.count("COMMIT;") == 1, path.name


def test_the_numbering_is_derived_from_canonical_main_not_from_the_failed_lineage():
    """canonical main ended at 039, so this slice starts at 040. The failed branch's own 040/041
    are not history this lineage has.

    Amended by AT-M3.5, which adds 042. The original also asserted ``numbers[-1] == 41``, which
    said "no migration after 041 exists anywhere in the repository" -- true when written, and never
    what this test was about. That clause made every future slice's first migration fail an AT-M3.4
    test, which is a numbering claim about the whole repository living inside a slice-scoped file.
    What the test actually defends is that AT-M3.4 owns 040 and 041, each exactly once, directly
    after the 039 it derived from, and that is what is asserted now. No AT-M3.4 contract, schema,
    constraint or behaviour is touched.
    """
    numbers = sorted(
        int(p.name[:3])
        for p in (ROOT / "migrations").glob("*.sql")
        if p.name[:3].isdigit() and not p.name.endswith("_down.sql")
    )
    assert numbers.count(39) == 1, "the base this slice derived from must still be there, once"
    assert numbers.count(40) == 1 and numbers.count(41) == 1
    assert _DURABLE.name.startswith("040_") and _FORWARD.name.startswith("041_")


# --- 040: the durable reasoning artifact ------------------------------------------------------


def test_040_alters_only_the_reasoning_table_and_creates_nothing():
    body = _sql_body(_DURABLE)
    assert "CREATE TABLE" not in body.upper()
    assert "DROP COLUMN" not in body.upper()
    assert "DELETE FROM" not in body.upper()
    assert "reasoning_invocations" in body
    # AT-D14's one schema prohibition is on further AT-M2 alteration.
    for other in ("team_messages", "team_decisions", "plan_revisions", "discussion_sessions"):
        assert f"ALTER TABLE {other}" not in body, other


def test_the_success_invariant_is_a_database_check_not_a_convention():
    body = _sql_body(_DURABLE)
    assert "chk_reasoning_invocations_success_artifact" in body
    assert "status = 'succeeded' AND artifact_type IS NOT NULL AND artifact IS NOT NULL" in body
    assert "status <> 'succeeded' AND artifact_type IS NULL AND artifact IS NULL" in body


def test_the_legacy_strategy_is_stated_and_is_not_a_rewrite():
    """Old metadata-only successes are preserved, so the invariant is added NOT VALID. What must
    NOT appear is any attempt to fabricate, delete or relabel them."""
    body = _sql_body(_DURABLE)
    assert body.count("NOT VALID") == 2, "exactly the two constraints legacy rows can violate"
    assert "chk_reasoning_invocations_success_artifact CHECK" in body
    assert "chk_reasoning_invocations_lease CHECK" in body
    assert "UPDATE reasoning_invocations SET status" not in body
    assert "DELETE FROM reasoning_invocations" not in body
    # The compatibility choice is documented in the file itself, not only in a report.
    prose = _DURABLE.read_text(encoding="utf-8")
    assert "LEGACY ROWS" in prose and "NOT VALID" in prose


def test_the_artifact_type_vocabulary_is_explicit_per_verb():
    body = _sql_body(_DURABLE)
    assert "chk_reasoning_invocations_artifact_type" in body
    for verb, artifact in (
        ("propose", "ProposalArtifact"),
        ("critique", "CritiqueArtifact"),
        ("summarize_decision", "DecisionSummaryArtifact"),
        ("decompose_plan", "PlanDraftArtifact"),
    ):
        assert f"reasoning_verb = '{verb}' AND artifact_type = '{artifact}'" in body, verb


def test_the_verb_is_widened_and_the_canonical_037_is_not_rewritten():
    body = _sql_body(_DURABLE)
    assert "'propose', 'critique', 'summarize_decision', 'decompose_plan'" in body
    original = _sql_body(ROOT / "migrations" / "037_at_m3_reasoning_invocations.sql")
    assert "decompose_plan" not in original, "037 is merged history and is never edited"
    assert "artifact" not in original, "037 declares no artifact column; 040 adds it"


def test_the_lease_columns_exist_and_terminal_rows_own_nothing():
    body = _sql_body(_DURABLE)
    for column in ("attempt", "attempt_token", "lease_expires_at"):
        assert f"ADD COLUMN IF NOT EXISTS {column}" in body or f"IF NOT EXISTS {column} " in body, (
            column
        )
    assert "chk_reasoning_invocations_lease" in body
    assert "status <> 'started' AND lease_expires_at IS NULL" in body
    assert "chk_reasoning_invocations_attempt CHECK (attempt >= 1)" in body


def test_a_terminal_invocation_is_frozen_by_a_trigger():
    body = _sql_body(_DURABLE)
    assert "reasoning_invocations_enforce_terminal" in body
    assert "trg_reasoning_invocations_terminal" in body
    for column in ("status", "artifact_type", "artifact", "attempt", "attempt_token"):
        assert f"NEW.{column}" in body, column
    assert "restrict_violation" in body


def test_the_lifecycle_foreign_keys_are_not_frozen_by_that_trigger():
    """project_id/thread_id are ON DELETE SET NULL. Freezing them would make deleting a project
    fail against reasoning history rather than detach from it."""
    trigger = _sql_body(_DURABLE).split("reasoning_invocations_enforce_terminal")[1]
    trigger = trigger.split("$fn$ LANGUAGE plpgsql")[0]
    for column in ("project_id", "thread_id", "requested_by_principal_id"):
        assert f"NEW.{column}" not in trigger, column


def test_no_hidden_reasoning_column_is_added_by_the_durability_migration():
    body = _sql_body(_DURABLE).lower()
    for forbidden in (
        "chain_of_thought",
        "hidden_reasoning",
        "scratchpad",
        "raw_prompt",
        "system_prompt",
        "raw_completion",
        "token_trace",
        "credential",
        "api_key",
        "secret",
    ):
        assert forbidden not in body, forbidden


def test_the_durability_down_migration_refuses_to_destroy_reasoning_evidence():
    body = _sql_body(_DURABLE_DOWN)
    assert body.upper().count("RAISE EXCEPTION") == 3
    assert "DELETE FROM" not in body.upper()
    assert "artifact IS NOT NULL" in body
    assert "reasoning_verb = 'decompose_plan'" in body
    assert "attempt > 1" in body
    # And when it is safe to run, it restores 037's own vocabulary exactly.
    assert "'propose', 'critique', 'summarize_decision'\n    ));" in body


# --- 041: the planning decision ledger ---------------------------------------------------------


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
        line
        for line in sql.splitlines()
        if "candidate_plan_message_id" in line and "REFERENCES" in line
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


def test_the_canonical_migrations_are_untouched():
    """001-039 are merged history. A new invariant is a new file, never an edit to an applied one."""
    import subprocess

    changed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "83ae97fd273c0506aac067b3c13dbaff19933bc9",
            "--",
            "migrations/",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if changed.returncode != 0:
        return  # not a git checkout; the static assertions above still hold
    touched = [line for line in changed.stdout.splitlines() if line.strip()]
    for path in touched:
        number = Path(path).name[:3]
        assert number.isdigit() and int(number) >= 40, f"canonical migration modified: {path}"
