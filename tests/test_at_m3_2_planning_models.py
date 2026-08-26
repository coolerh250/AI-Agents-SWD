"""Step AT-M3.2 -- Goal / PlanRevision domain models and the structured diff.

Pure model tests: no database, no network, no provider. The store-level guarantees that only a
real PostgreSQL can prove (immutability, lineage constraints, the concurrent successor race) live
in tests/test_at_m3_2_planning_store.py and are deliberately NOT simulated here -- an in-memory
fake asserting a UNIQUE constraint would be asserting its own behaviour.
"""

from __future__ import annotations

import uuid

import pytest

from shared.sdk.agent_planning.models import (
    REPLAN_REASONS,
    Goal,
    PlanContent,
    PlanDiff,
    PlanRevision,
    PlanStep,
    PlanStepDraftError,
    StalePlanRevisionError,
    compute_plan_diff,
    parse_plan,
)


def _plan(**overrides) -> dict:
    base = {
        "objective": "Ship a working clarification inbox",
        "steps": [
            {
                "step_key": "design",
                "title": "Design the inbox",
                "required_capabilities": ["design_review"],
                "expected_outputs": ["design brief"],
                "depends_on": [],
            },
            {
                "step_key": "build",
                "title": "Build the inbox",
                "required_capabilities": ["backend_implementation"],
                "expected_outputs": ["api"],
                "depends_on": ["design"],
            },
        ],
        "constraints": ["no production action"],
        "acceptance_criteria": ["operator can read the inbox"],
    }
    base.update(overrides)
    return base


# --- structured plan ---------------------------------------------------------------------------


def test_plan_content_is_structured_not_prose():
    content = PlanContent.model_validate(_plan())
    assert content.objective
    assert [step.step_key for step in content.steps] == ["design", "build"]
    assert content.steps[1].depends_on == ("design",)
    assert content.steps[1].required_capabilities == ("backend_implementation",)


def test_plan_rejects_unknown_fields():
    """Closed schema: a caller cannot smuggle an extra key past the contract."""
    with pytest.raises(Exception):
        PlanContent.model_validate(_plan(unexpected_field="x"))


def test_plan_rejects_duplicate_step_keys():
    steps = [
        {"step_key": "a", "title": "one"},
        {"step_key": "a", "title": "two"},
    ]
    with pytest.raises(PlanStepDraftError):
        parse_plan(_plan(steps=steps))


def test_plan_rejects_dependency_on_unknown_step():
    steps = [{"step_key": "a", "title": "one", "depends_on": ["ghost"]}]
    with pytest.raises(PlanStepDraftError):
        parse_plan(_plan(steps=steps))


def test_plan_rejects_self_dependency():
    steps = [{"step_key": "a", "title": "one", "depends_on": ["a"]}]
    with pytest.raises(PlanStepDraftError):
        parse_plan(_plan(steps=steps))


def test_plan_step_rejects_unknown_fields():
    with pytest.raises(Exception):
        PlanStep.model_validate({"step_key": "a", "title": "t", "scratchpad": "..."})


# --- content safety (INV-04 / AT-D03 R8) --------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden",
    ["chain_of_thought", "scratchpad", "system_prompt", "api_key", "raw_prompt", "credential"],
)
def test_plan_rejects_hidden_reasoning_and_secret_key_names(forbidden):
    """The closed schema stops these first; assert_content_is_safe is the store-layer backstop."""
    from shared.sdk.agent_team.models import assert_content_is_safe

    with pytest.raises(ValueError):
        assert_content_is_safe({"objective": "x", forbidden: "leak"}, field="plan")


def test_diff_payload_is_screened_for_forbidden_keys():
    from shared.sdk.agent_team.models import assert_content_is_safe

    with pytest.raises(ValueError):
        assert_content_is_safe({"steps_added": ["a"], "hidden_reasoning": "..."}, field="diff")


# --- structured diff ---------------------------------------------------------------------------


def test_diff_detects_step_added_and_removed():
    before = PlanContent.model_validate(_plan())
    after = PlanContent.model_validate(
        _plan(
            steps=[
                {
                    "step_key": "design",
                    "title": "Design the inbox",
                    "required_capabilities": ["design_review"],
                    "expected_outputs": ["design brief"],
                },
                {"step_key": "test", "title": "Test the inbox", "depends_on": ["design"]},
            ]
        )
    )
    diff = compute_plan_diff(before, after)
    assert diff.steps_added == ("test",)
    assert diff.steps_removed == ("build",)
    assert not diff.is_empty


def test_diff_detects_modified_step_fields():
    before = PlanContent.model_validate(_plan())
    after_steps = _plan()["steps"]
    after_steps[1] = dict(after_steps[1], title="Build the inbox, carefully")
    after = PlanContent.model_validate(_plan(steps=after_steps))
    diff = compute_plan_diff(before, after)
    assert [change.step_key for change in diff.steps_modified] == ["build"]
    assert diff.steps_modified[0].changed_fields == ("title",)


def test_diff_detects_capability_requirement_change():
    before = PlanContent.model_validate(_plan())
    after_steps = _plan()["steps"]
    after_steps[1] = dict(after_steps[1], required_capabilities=["qa_verification"])
    after = PlanContent.model_validate(_plan(steps=after_steps))
    diff = compute_plan_diff(before, after)
    assert diff.capability_requirements_changed == ("build",)
    assert "required_capabilities" in diff.steps_modified[0].changed_fields


def test_diff_detects_dependency_change():
    before = PlanContent.model_validate(_plan())
    after_steps = _plan()["steps"]
    after_steps[1] = dict(after_steps[1], depends_on=[])
    after = PlanContent.model_validate(_plan(steps=after_steps))
    diff = compute_plan_diff(before, after)
    assert diff.dependencies_removed == ("design->build",)
    assert diff.dependencies_added == ()


def test_diff_detects_ownership_intent_change():
    before = PlanContent.model_validate(_plan())
    after_steps = _plan()["steps"]
    after_steps[0] = dict(after_steps[0], intended_owner_role="qa")
    after = PlanContent.model_validate(_plan(steps=after_steps))
    diff = compute_plan_diff(before, after)
    assert diff.ownership_changed == ("design",)


def test_diff_detects_objective_and_constraint_change():
    before = PlanContent.model_validate(_plan())
    after = PlanContent.model_validate(
        _plan(objective="Ship something else", constraints=["no external call"])
    )
    diff = compute_plan_diff(before, after)
    assert diff.objective_changed is True
    assert diff.constraints_changed is True


def test_diff_of_identical_plans_is_empty():
    before = PlanContent.model_validate(_plan())
    after = PlanContent.model_validate(_plan())
    assert compute_plan_diff(before, after).is_empty is True


def test_diff_is_deterministic():
    before = PlanContent.model_validate(_plan())
    after = PlanContent.model_validate(_plan(objective="changed"))
    assert (
        compute_plan_diff(before, after).model_dump()
        == compute_plan_diff(before, after).model_dump()
    )


def test_diff_carries_a_rationale_conclusion_not_a_trace():
    before = PlanContent.model_validate(_plan())
    after = PlanContent.model_validate(_plan(objective="changed"))
    diff = compute_plan_diff(before, after, rationale="the goal was amended by the requester")
    assert diff.rationale == "the goal was amended by the requester"
    # No field on the diff can hold a reasoning trace: the schema is closed.
    assert set(PlanDiff.model_fields) == {
        "steps_added",
        "steps_removed",
        "steps_modified",
        "dependencies_added",
        "dependencies_removed",
        "capability_requirements_changed",
        "ownership_changed",
        "objective_changed",
        "constraints_changed",
        "acceptance_criteria_changed",
        "rationale",
    }


# --- revision lineage semantics -----------------------------------------------------------------


def _revision(**overrides) -> dict:
    base = {
        "plan_revision_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "goal_id": uuid.uuid4(),
        "revision_number": 1,
        "created_by": uuid.uuid4(),
        "reason": "initial",
        "supersedes_revision_id": None,
        "status": "draft",
        "plan": _plan(),
    }
    base.update(overrides)
    return base


def test_initial_reason_means_root_revision():
    rev = PlanRevision.model_validate(_revision())
    assert rev.is_root is True


def test_successor_may_not_claim_initial():
    with pytest.raises(ValueError):
        PlanRevision.model_validate(
            _revision(reason="initial", supersedes_revision_id=uuid.uuid4())
        )


def test_root_may_not_claim_a_replan_cause():
    with pytest.raises(ValueError):
        PlanRevision.model_validate(_revision(reason="team_decision", supersedes_revision_id=None))


def test_revision_may_not_supersede_itself():
    rev_id = uuid.uuid4()
    with pytest.raises(ValueError):
        PlanRevision.model_validate(
            _revision(
                plan_revision_id=rev_id, reason="team_decision", supersedes_revision_id=rev_id
            )
        )


def test_superseded_is_not_a_writable_status():
    """Supersession is derived from lineage, so 'superseded' must not be an authored status."""
    with pytest.raises(ValueError):
        PlanRevision.model_validate(_revision(status="superseded"))


def test_replan_reasons_match_the_architecture_contract():
    assert REPLAN_REASONS == {
        "goal_changed",
        "clarification_answered",
        "team_decision",
        "debug_plan_invalid",
        "dependency_discovered",
        "scope_correction",
        "blocked_resolution",
    }


def test_debug_plan_invalid_is_available_but_unused_by_this_slice():
    """M4 supplies the trigger; M3.2 only records that the vocabulary exists."""
    assert "debug_plan_invalid" in REPLAN_REASONS


# --- goal ----------------------------------------------------------------------------------------


def test_goal_is_intent_not_work():
    goal = Goal(
        goal_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        statement="Deliver a clarification inbox",
        acceptance_criteria=("operator can read it",),
        constraints=("no production action",),
        created_by=uuid.uuid4(),
    )
    assert goal.status == "draft"
    # A Goal owns no work: no owner, no run, no work-item field exists on it.
    assert not {"owner_principal_id", "work_item_id", "run_id"} & set(Goal.model_fields)


def test_goal_rejects_unknown_fields():
    with pytest.raises(Exception):
        Goal.model_validate(
            {
                "goal_id": uuid.uuid4(),
                "project_id": uuid.uuid4(),
                "statement": "x",
                "created_by": uuid.uuid4(),
                "work_item_id": uuid.uuid4(),
            }
        )


def test_stale_error_names_both_revisions():
    expected, actual, goal = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    err = StalePlanRevisionError(expected=expected, actual=actual, goal_id=goal)
    assert err.expected_revision_id == str(expected)
    assert err.actual_revision_id == str(actual)
    assert str(expected) in str(err) and str(actual) in str(err)
