"""Step AT-M3.2 -- Goal and immutable PlanRevision domain models.

Implements docs/architecture/autonomous-team/planning-and-plan-revision-model.md sections 2, 3, 5
and 6 (AT-D04), authorized by AT-D14. Names follow that contract; no parallel Project/WorkItem
hierarchy is introduced -- a Goal hangs off the existing ``projects`` row and owns no work.

INV-04 (AT-D03 R8), restated for every M3 slice by AT-D14 section 4: nothing here carries hidden
reasoning. ``PlanContent`` and ``PlanDiff`` are closed schemas (``extra="forbid"``) AND are
key-screened with the AT-M2 ``assert_content_is_safe`` helper rather than a second, parallel
mechanism -- the same defence AT-M3.1 reused for its artifacts.

The plan is deliberately structured rather than prose. M3.4 has to generate work items from it and
M3.5 has to dispatch per work item against it; a text blob would make both of those a parsing
problem instead of a data problem. This slice defines the structure and stores it. It performs no
decomposition and no dispatch -- those are M3.4 and M3.5.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from shared.sdk.agent_team.models import assert_content_is_safe

GoalStatus = Literal["draft", "active", "achieved", "abandoned"]

#: A revision's authored lifecycle status. ``superseded`` is deliberately NOT here: a revision is
#: superseded exactly when another revision names it, which is a fact about the lineage. Deriving
#: it costs one query; storing it would cost an UPDATE on an append-only row.
PlanRevisionStatus = Literal["draft", "proposed", "accepted", "rejected"]

#: Why a revision exists (contract section 5). ``debug_plan_invalid`` is the load-bearing one --
#: it is what will make the M4 loop a loop rather than a retry. This slice records the vocabulary;
#: it triggers none of them automatically.
PlanRevisionReason = Literal[
    "initial",
    "goal_changed",
    "clarification_answered",
    "team_decision",
    "debug_plan_invalid",
    "dependency_discovered",
    "scope_correction",
    "blocked_resolution",
]

REPLAN_REASONS: frozenset[str] = frozenset(
    {
        "goal_changed",
        "clarification_answered",
        "team_decision",
        "debug_plan_invalid",
        "dependency_discovered",
        "scope_correction",
        "blocked_resolution",
    }
)


class PlanStepDraftError(ValueError):
    """A plan is structurally invalid -- duplicate step keys, or a dependency on nothing.

    Raised by :func:`parse_plan`, which is how every caller in this package builds a
    ``PlanContent``. Pydantic wraps an exception raised inside a model validator in its own
    ``ValidationError``, so raising this type from the validator alone would mean no caller could
    ever catch it -- an error class nobody can catch is worse than no error class at all.
    """


class PlanStep(BaseModel):
    """One unit of intended work inside a plan.

    Not a WorkItem. M3.4 generates WorkItems from these; until then a step is planning intent with
    no runtime row, no owner assignment and no dispatch. ``intended_owner_role`` records what the
    plan *wants*, which the M3.5 capability router is free to override -- recording an intent is
    not assigning an owner, and a human does not assign owners in normal autonomous flow (D04-R9).
    """

    model_config = ConfigDict(extra="forbid")

    step_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    #: What the step needs a principal to be able to do. Matched by the AT-M2 capability router in
    #: M3.5; here it is declared intent only.
    required_capabilities: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    #: step_key values this step depends on. Validated for existence at the plan level below.
    depends_on: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    intended_owner_role: str | None = Field(default=None, max_length=100)


class PlanContent(BaseModel):
    """The structured plan a revision carries.

    Ordered by ``steps`` position AND dependency-aware via ``depends_on`` -- both, because a plan
    that only has an order cannot express parallelism and a plan that only has dependencies cannot
    express a preferred sequence. M3.4's decomposition will populate this; M3.2 accepts it from a
    caller and stores it faithfully.
    """

    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1, max_length=2000)
    steps: tuple[PlanStep, ...] = ()
    constraints: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_structure(self) -> PlanContent:
        keys = [step.step_key for step in self.steps]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise PlanStepDraftError(f"duplicate step_key(s): {duplicates}")
        known = set(keys)
        for step in self.steps:
            unknown = sorted(set(step.depends_on) - known)
            if unknown:
                raise PlanStepDraftError(
                    f"step '{step.step_key}' depends on unknown step(s): {unknown}"
                )
            if step.step_key in step.depends_on:
                raise PlanStepDraftError(f"step '{step.step_key}' depends on itself")
        assert_content_is_safe(self.model_dump(mode="json"), field="plan")
        return self


class StepChange(BaseModel):
    """One modified step, described by WHICH fields changed -- never by a prose summary."""

    model_config = ConfigDict(extra="forbid")

    step_key: str
    changed_fields: tuple[str, ...]


class PlanDiff(BaseModel):
    """The structured change set between a predecessor revision and its successor.

    Contract section 6 names this over work items. At M3.2 no WorkItem rows exist yet -- M3.4
    creates them -- so the same diff semantics are expressed over the plan's own steps, which are
    what M3.4 will map to work items. ``steps_added``/``steps_removed``/``steps_modified`` are the
    contract's ``work_items_added``/``removed``/``modified`` one layer earlier in the pipeline.

    Plan-state changes only. ``rationale`` is a conclusion the author stands behind, in the same
    sense as ``TeamDecision.rationale_summary`` -- never a reasoning trace, and screened as such.
    """

    model_config = ConfigDict(extra="forbid")

    steps_added: tuple[str, ...] = ()
    steps_removed: tuple[str, ...] = ()
    steps_modified: tuple[StepChange, ...] = ()
    dependencies_added: tuple[str, ...] = ()
    dependencies_removed: tuple[str, ...] = ()
    capability_requirements_changed: tuple[str, ...] = ()
    ownership_changed: tuple[str, ...] = ()
    objective_changed: bool = False
    constraints_changed: bool = False
    acceptance_criteria_changed: bool = False
    rationale: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _validate_safe(self) -> PlanDiff:
        assert_content_is_safe(self.model_dump(mode="json"), field="diff")
        return self

    @property
    def is_empty(self) -> bool:
        """True when the successor's plan is materially identical to its predecessor's."""
        return not (
            self.steps_added
            or self.steps_removed
            or self.steps_modified
            or self.dependencies_added
            or self.dependencies_removed
            or self.capability_requirements_changed
            or self.ownership_changed
            or self.objective_changed
            or self.constraints_changed
            or self.acceptance_criteria_changed
        )


_COMPARED_STEP_FIELDS = (
    "title",
    "description",
    "expected_outputs",
    "constraints",
)


def _dependency_edges(plan: PlanContent) -> set[str]:
    return {f"{parent}->{step.step_key}" for step in plan.steps for parent in step.depends_on}


def compute_plan_diff(
    previous: PlanContent, current: PlanContent, *, rationale: str | None = None
) -> PlanDiff:
    """The structured change set from ``previous`` to ``current``.

    Deterministic and total: the same pair always produces the same diff, and every difference the
    plan schema can express lands in exactly one field. Computed server-side rather than accepted
    from the caller -- a caller-supplied diff could disagree with the plan it claims to describe,
    and the diff is the thing a human reviews instead of reading two full plans.
    """
    before = {step.step_key: step for step in previous.steps}
    after = {step.step_key: step for step in current.steps}

    added = tuple(sorted(set(after) - set(before)))
    removed = tuple(sorted(set(before) - set(after)))

    modified: list[StepChange] = []
    capability_changed: list[str] = []
    ownership_changed: list[str] = []
    for key in sorted(set(before) & set(after)):
        old, new = before[key], after[key]
        changed = [
            field for field in _COMPARED_STEP_FIELDS if getattr(old, field) != getattr(new, field)
        ]
        if old.required_capabilities != new.required_capabilities:
            changed.append("required_capabilities")
            capability_changed.append(key)
        if old.intended_owner_role != new.intended_owner_role:
            changed.append("intended_owner_role")
            ownership_changed.append(key)
        if changed:
            modified.append(StepChange(step_key=key, changed_fields=tuple(sorted(changed))))

    edges_before = _dependency_edges(previous)
    edges_after = _dependency_edges(current)

    return PlanDiff(
        steps_added=added,
        steps_removed=removed,
        steps_modified=tuple(modified),
        dependencies_added=tuple(sorted(edges_after - edges_before)),
        dependencies_removed=tuple(sorted(edges_before - edges_after)),
        capability_requirements_changed=tuple(capability_changed),
        ownership_changed=tuple(ownership_changed),
        objective_changed=previous.objective != current.objective,
        constraints_changed=previous.constraints != current.constraints,
        acceptance_criteria_changed=previous.acceptance_criteria != current.acceptance_criteria,
        rationale=rationale,
    )


def parse_plan(payload: Any) -> PlanContent:
    """Build a validated :class:`PlanContent`, surfacing structural defects as
    :class:`PlanStepDraftError`.

    A duplicate step key, a dependency on a step that does not exist, and a self-dependency are
    plan-authoring mistakes a caller can fix; a wrong type or an unknown field is a contract
    violation. Both are ``ValueError``s, so an API layer may treat them identically -- but only
    the first is worth naming, and naming it costs one function.
    """
    try:
        return PlanContent.model_validate(payload)
    except ValidationError as exc:
        for error in exc.errors():
            cause = error.get("ctx", {}).get("error")
            if isinstance(cause, PlanStepDraftError):
                raise cause from exc
        raise


class Goal(BaseModel):
    """The human/system intent the team serves. Intent, never work (contract section 2)."""

    model_config = ConfigDict(extra="forbid")

    goal_id: UUID
    project_id: UUID
    statement: str = Field(min_length=1, max_length=4000)
    acceptance_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    created_by: UUID
    status: GoalStatus = "draft"
    audit_ref: str | None = None
    created_at: datetime | None = None


class PlanRevision(BaseModel):
    """One immutable revision of a plan.

    ``is_current`` and ``is_superseded`` are DERIVED by the store from lineage and passed in; they
    are not columns. A model instance is a read view of an append-only row -- constructing one
    never implies the row can be written back.
    """

    model_config = ConfigDict(extra="forbid")

    plan_revision_id: UUID
    project_id: UUID
    goal_id: UUID
    revision_number: int = Field(ge=1)
    created_by: UUID
    reason: PlanRevisionReason
    supersedes_revision_id: UUID | None = None
    status: PlanRevisionStatus = "draft"
    plan: PlanContent
    diff: PlanDiff = PlanDiff()
    trace_ref: str | None = None
    audit_ref: str | None = None
    created_at: datetime | None = None
    #: Derived from lineage: no other revision names this one.
    is_current: bool = False

    @property
    def is_root(self) -> bool:
        return self.supersedes_revision_id is None

    @model_validator(mode="after")
    def _validate_lineage(self) -> PlanRevision:
        if (self.reason == "initial") != (self.supersedes_revision_id is None):
            raise ValueError(
                "reason 'initial' means exactly 'root revision': a successor may not claim it, "
                "and a root may not claim another cause"
            )
        if self.supersedes_revision_id == self.plan_revision_id:
            raise ValueError("a revision may not supersede itself")
        return self


class StalePlanRevisionError(RuntimeError):
    """A successor was derived from a revision that is no longer current -- fail closed.

    Carries the revision the caller believed was current and the one that actually is, so the
    caller can re-derive rather than guess. Never retried automatically: a stale plan means the
    caller planned against a world that has since changed, and silently rebasing its work onto the
    real current revision would produce a plan nobody authored.
    """

    def __init__(self, *, expected: Any, actual: Any, goal_id: Any) -> None:
        self.expected_revision_id = str(expected) if expected is not None else None
        self.actual_revision_id = str(actual) if actual is not None else None
        self.goal_id = str(goal_id)
        super().__init__(
            f"stale plan revision for goal {self.goal_id}: caller expected "
            f"{self.expected_revision_id} to be current, but the current revision is "
            f"{self.actual_revision_id}"
        )


class PlanLineageError(ValueError):
    """A predecessor that does not exist, or belongs to a different goal."""


__all__ = [
    "Goal",
    "GoalStatus",
    "PlanContent",
    "PlanDiff",
    "PlanLineageError",
    "PlanRevision",
    "PlanRevisionReason",
    "PlanRevisionStatus",
    "PlanStep",
    "PlanStepDraftError",
    "REPLAN_REASONS",
    "StalePlanRevisionError",
    "StepChange",
    "compute_plan_diff",
    "parse_plan",
]
