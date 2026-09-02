"""Step AT-M3.5 -- what migration 042 must and must not contain.

Static, so it runs without a database. It asserts the things a reviewer would otherwise have to
take on trust: that the load-bearing uniqueness is really unique, that a Goal has exactly one
execution root, that a dispatch is bound to the revision that authorized it and cannot be rewritten,
and -- most importantly -- that no second work-item model, task authority, routing table, workflow
model or capability registry was invented on the way here.

Numbering is derived from canonical main, which ends at 041 (AT-M3.4). This slice is 042.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FORWARD = ROOT / "migrations" / "042_at_m3_5_plan_execution_graph.sql"
_DOWN = ROOT / "migrations" / "042_at_m3_5_plan_execution_graph_down.sql"


def _sql_body(path: Path) -> str:
    """The SQL with prose removed, so a mention is never read as a declaration."""
    kept: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("--"):
            continue
        kept.append(line)
    return "\n".join(kept)


FORWARD = _sql_body(_FORWARD)
DOWN = _sql_body(_DOWN)


def test_both_migration_files_exist_and_are_transactional():
    for path in (_FORWARD, _DOWN):
        sql = path.read_text(encoding="utf-8")
        assert sql.count("BEGIN;") == 1 and sql.count("COMMIT;") == 1, path.name


def test_the_numbering_is_derived_from_canonical_main():
    """Canonical main ended at 041 (AT-M3.4), so this slice is 042, once.

    Deliberately NOT ``numbers[-1] == 42``: that would say "no migration after 042 exists", which
    is a claim about the whole repository rather than about this slice, and it would fail the
    moment AT-M3.6 adds its first migration. AT-M3.4's equivalent assertion had exactly that shape
    and AT-M3.5 is what broke it.
    """
    numbers = sorted(
        int(p.name[:3])
        for p in (ROOT / "migrations").glob("*.sql")
        if p.name[:3].isdigit() and not p.name.endswith("_down.sql")
    )
    assert numbers.count(41) == 1, "the base this slice derived from must still be there, once"
    assert numbers.count(42) == 1
    assert _FORWARD.name.startswith("042_") and _DOWN.name.startswith("042_")


def test_it_creates_exactly_the_four_tables_this_slice_needs():
    created = {
        line.split("CREATE TABLE IF NOT EXISTS ")[1].split()[0].strip("(")
        for line in FORWARD.splitlines()
        if "CREATE TABLE IF NOT EXISTS" in line
    }
    assert created == {
        "goal_execution_lineage",
        "plan_execution_graphs",
        "plan_execution_units",
        "plan_execution_dispatches",
    }


def test_it_adds_no_column_to_and_drops_nothing_from_any_existing_table():
    assert "ALTER TABLE" not in FORWARD
    assert "DROP TABLE" not in FORWARD
    assert "DROP COLUMN" not in FORWARD


# --- what was reused rather than rebuilt ------------------------------------------------------


def test_no_second_work_item_task_workflow_or_routing_model_is_created():
    """The whole point of the slice is that a plan step becomes an EXISTING work item, owned by an
    EXISTING routing decision, under an EXISTING project. A table that duplicated any of those
    would be the second execution lineage AT-D01 forbids."""
    forbidden = (
        "CREATE TABLE IF NOT EXISTS work_items",
        "CREATE TABLE IF NOT EXISTS project_work_items",
        "CREATE TABLE IF NOT EXISTS plan_work_items",
        "CREATE TABLE IF NOT EXISTS tasks",
        "CREATE TABLE IF NOT EXISTS plan_tasks",
        "CREATE TABLE IF NOT EXISTS workflow",
        "CREATE TABLE IF NOT EXISTS plan_revision_runs",
        "CREATE TABLE IF NOT EXISTS agent_routing",
        "CREATE TABLE IF NOT EXISTS agent_capabilities",
        "CREATE TABLE IF NOT EXISTS plan_execution_unit_dependencies",
    )
    for statement in forbidden:
        assert statement not in FORWARD, statement


def test_the_existing_work_item_and_routing_tables_are_referenced_not_replaced():
    assert "REFERENCES project_work_items(id)" in FORWARD
    assert "REFERENCES agent_routing_decisions(routing_decision_id)" in FORWARD
    assert "REFERENCES actor_principals(principal_id)" in FORWARD
    assert "REFERENCES plan_revisions" in FORWARD


def test_no_stale_or_currency_column_is_introduced():
    """Currency is derived from lineage (planning-and-plan-revision-model.md 11b). A stored copy
    would be the first one anywhere in this model, and would need a writer and a repair path."""
    for column in ("is_current", "is_stale", "superseded", "current_revision", "is_superseded"):
        assert column not in FORWARD.lower().replace("supersedes_revision_id", "")


# --- the load-bearing uniqueness ---------------------------------------------------------------


def test_one_graph_per_plan_revision():
    assert "CONSTRAINT uq_peg_plan_revision UNIQUE (plan_revision_id)" in FORWARD


def test_exact_step_identity_is_unique_per_revision():
    assert "CONSTRAINT uq_peu_revision_step UNIQUE (plan_revision_id, step_key)" in FORWARD


def test_one_canonical_dispatch_per_execution_unit():
    assert "execution_unit_id     UUID PRIMARY KEY" in FORWARD
    assert "CONSTRAINT uq_ped_correlation UNIQUE (correlation_id)" in FORWARD


def test_a_goal_has_exactly_one_primary_work_item():
    assert "goal_id               UUID PRIMARY KEY REFERENCES goals(goal_id)" in FORWARD
    assert "CONSTRAINT uq_gel_primary_work_item UNIQUE (primary_work_item_id)" in FORWARD


def test_a_work_item_belongs_to_at_most_one_plan_step():
    assert "CONSTRAINT uq_peu_work_item UNIQUE (work_item_id)" in FORWARD


def test_a_graph_cannot_claim_a_revision_from_another_goal_or_project():
    assert "CONSTRAINT fk_peg_revision_goal FOREIGN KEY (plan_revision_id, goal_id)" in FORWARD
    assert "CONSTRAINT fk_peg_goal_lineage FOREIGN KEY (goal_id, project_id)" in FORWARD


def test_a_unit_cannot_be_moved_between_graphs_of_different_revisions():
    assert (
        "CONSTRAINT fk_peu_graph_revision FOREIGN KEY (plan_execution_graph_id, plan_revision_id)"
        in FORWARD
    )


# --- immutability -------------------------------------------------------------------------------


def test_the_execution_root_the_graph_the_unit_identity_and_the_dispatch_are_all_frozen():
    for trigger in (
        "trg_gel_freeze",
        "trg_peg_append_only",
        "trg_peu_freeze_identity",
        "trg_ped_append_only",
    ):
        assert f"CREATE TRIGGER {trigger}" in FORWARD, trigger


def test_a_terminal_unit_cannot_be_moved_again():
    assert "a terminal unit may not be moved again" in _FORWARD.read_text(encoding="utf-8")


def test_the_state_vocabulary_is_exactly_the_seven_this_slice_defines():
    assert (
        "'blocked', 'ready', 'assigned', 'dispatched', 'completed', 'failed', 'cancelled'"
        in FORWARD
    )


def test_an_assigned_or_dispatched_unit_must_have_an_owner():
    assert "CONSTRAINT chk_peu_assigned_shape" in FORWARD


def test_a_unit_cannot_be_both_owned_and_unassignable():
    assert "CONSTRAINT chk_peu_unavailable_shape" in FORWARD


def test_a_graph_with_no_steps_is_unrepresentable():
    assert "CONSTRAINT chk_peg_step_count CHECK (step_count >= 1)" in FORWARD


# --- storage prohibition -------------------------------------------------------------------------


def test_no_column_can_hold_reasoning_a_transcript_a_secret_or_a_plan_body():
    lowered = FORWARD.lower()
    for marker in (
        "chain_of_thought",
        "raw_prompt",
        "system_prompt",
        "scratchpad",
        "completion",
        "transcript",
        "api_key",
        "credential",
        "password",
        "plan_content",
        "plan  ",
    ):
        assert marker not in lowered, marker


def test_no_column_can_hold_a_command_a_patch_or_an_external_target():
    """AT-M3.5 decides what/when/who. A column able to carry HOW would be AT-M4 leakage in the
    schema, reachable long before any code used it.

    Matched on whole words: ``dispatched`` contains ``patch``, and a substring scan would report
    the state vocabulary as a smuggled diff.
    """
    words = set(re.findall(r"[a-z_]+", FORWARD.lower()))
    for marker in (
        "command",
        "shell",
        "script",
        "patch",
        "diff",
        "repository_url",
        "pull_request",
        "deployment",
        "webhook",
    ):
        assert marker not in words, marker


# --- the down migration ---------------------------------------------------------------------------


def test_the_down_migration_drops_this_slices_tables_and_nothing_else():
    dropped = {
        line.split("DROP TABLE IF EXISTS ")[1].strip().rstrip(";")
        for line in DOWN.splitlines()
        if "DROP TABLE IF EXISTS" in line
    }
    assert dropped == {
        "goal_execution_lineage",
        "plan_execution_graphs",
        "plan_execution_units",
        "plan_execution_dispatches",
    }
    assert "ALTER TABLE" not in DOWN
    assert "DELETE FROM" not in DOWN


def test_the_down_migration_refuses_once_materialization_evidence_exists():
    """Independent Validation 1: DOWN used to drop the mapping and leave the business work items,
    so DOWN -> UP -> materialize created a second set of child work items for the same plan steps.

    The sequence is removed rather than repaired -- deleting the work items would destroy
    execution-lineage rows this slice does not own, and re-adopting orphans on UP would reattach
    work whose provenance was deleted. The live proof is in
    ``test_at_m3_5_migration_lifecycle.py``; this asserts the guard is present and unconditional.
    """
    assert "RAISE EXCEPTION" in DOWN
    assert "refusing to reverse migration 042" in DOWN
    for table in (
        "goal_execution_lineage",
        "plan_execution_graphs",
        "plan_execution_units",
        "plan_execution_dispatches",
    ):
        assert f"SELECT count(*) FROM {table}" in DOWN, table
    # No override, no force flag, no exemption: the only outcome is refuse-and-change-nothing.
    # Whole words -- ``plan_execution_dispatches_enforce_append_only`` contains "force".
    words = set(re.findall(r"[a-z_]+", DOWN.lower()))
    for escape in ("force", "override", "skip_check", "allow_data_loss", "bypass"):
        assert escape not in words, escape


def test_the_down_migration_still_deletes_no_business_rows():
    """Refusing is the fix. Deleting the work items would have been the other one, and it would
    destroy execution-lineage rows -- and, once AT-M4 exists, the Runs resolving to them."""
    assert "DELETE FROM" not in DOWN
    assert "TRUNCATE" not in DOWN.upper()


def test_the_down_migration_leaves_the_work_items_and_routing_evidence_alone():
    """Child work items, their dependency edges and the routing decisions belong to the project's
    own lineage, not to this ledger -- the same posture 041's down migration takes."""
    for table in (
        "project_work_items",
        "project_work_item_dependencies",
        "agent_routing_decisions",
        "work_item_events",
        "plan_revisions",
        "goals",
    ):
        assert f"DROP TABLE IF EXISTS {table}" not in DOWN
