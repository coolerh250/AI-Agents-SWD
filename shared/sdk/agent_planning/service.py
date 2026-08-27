"""Step AT-M3.2 -- Goal and PlanRevision runtime service.

The layer between the API and the store: it validates plan structure through the closed Pydantic
schemas, computes the structured diff server-side, and records an audit event per operation. It
performs no decomposition (M3.4), no dispatch (M3.5) and no reasoning call (M3.1 owns that) --
this slice makes planning DATA durable, not planning BEHAVIOUR autonomous.

Two deliberate refusals:

* **The diff is never accepted from the caller.** It is computed from the predecessor's stored
  plan and the submitted plan. A caller-supplied diff could disagree with the plan it claims to
  describe, and the diff is precisely what a human reads instead of two full plans.
* **A stale successor is never rebased.** ``StalePlanRevisionError`` propagates. Silently
  re-deriving the caller's plan onto the real current revision would produce a plan no principal
  authored, which is the opposite of traceable.

Audit degrades gracefully, matching ``TeamService``: a missing or failing audit sink must not stop
a plan being recorded, and must not silently turn a recorded revision into an unrecorded one --
the row is written first, and the audit reference is best-effort after it.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.agent_planning import events as planning_events
from shared.sdk.agent_planning.models import (
    Goal,
    PlanContent,
    PlanDiff,
    PlanLineageError,
    PlanRevision,
    StalePlanRevisionError,
    compute_plan_diff,
    parse_plan,
)
from shared.sdk.agent_planning.store import PlanningStore


class PlanningService:
    def __init__(
        self,
        store: Any | None = None,
        audit_client: Any | None = None,
    ) -> None:
        self.store = store if store is not None else PlanningStore()
        self.audit_client = audit_client

    # --- audit ---------------------------------------------------------------------------------

    async def _audit(
        self, decision_type: str, summary: str, result: str, refs: dict[str, Any]
    ) -> str | None:
        """Best-effort. Identifiers and disposition only -- never plan content or a rationale."""
        if self.audit_client is None:
            return None
        try:
            event = self.audit_client.build_audit_event(
                agent="planning-runtime",
                decision_type=decision_type,
                summary=summary,
                result=result,
                artifact_refs=refs,
            )
            return await self.audit_client.write_audit_event(event)
        except Exception:
            return None

    # --- goals ---------------------------------------------------------------------------------

    async def create_goal(
        self,
        *,
        project_id: str,
        statement: str,
        created_by: str,
        acceptance_criteria: tuple[str, ...] = (),
        constraints: tuple[str, ...] = (),
        status: str = "draft",
    ) -> dict[str, Any]:
        row = await self.store.create_goal(
            {
                "project_id": project_id,
                "statement": statement,
                "acceptance_criteria": acceptance_criteria,
                "constraints": constraints,
                "created_by": created_by,
                "status": status,
            }
        )
        await self._audit(
            planning_events.AUDIT_GOAL_CREATED,
            f"goal {row['goal_id']} created for project {row['project_id']}",
            "recorded",
            {
                "goal_id": str(row["goal_id"]),
                "project_id": str(row["project_id"]),
                "created_by": str(row["created_by"]),
            },
        )
        return row

    async def get_goal(self, goal_id: str) -> dict[str, Any] | None:
        return await self.store.get_goal(goal_id)

    # --- plan revisions ------------------------------------------------------------------------

    async def create_initial_revision(
        self,
        *,
        goal_id: str,
        created_by: str,
        plan: dict[str, Any],
        status: str = "draft",
        trace_ref: str | None = None,
    ) -> dict[str, Any]:
        """Revision 1 for a goal. Validated through ``PlanContent`` before it reaches the DB."""
        content = parse_plan(plan)
        row = await self.store.create_initial_revision(
            {
                "goal_id": goal_id,
                "created_by": created_by,
                "plan": content.model_dump(mode="json"),
                "status": status,
                "trace_ref": trace_ref,
            }
        )
        await self._audit(
            planning_events.AUDIT_PLAN_REVISION_CREATED,
            f"initial plan revision {row['plan_revision_id']} recorded for goal {goal_id}",
            "recorded",
            {
                "plan_revision_id": str(row["plan_revision_id"]),
                "goal_id": str(row["goal_id"]),
                "revision_number": str(row["revision_number"]),
                "reason": row["reason"],
                "supersedes_revision_id": None,
                "created_by": str(row["created_by"]),
            },
        )
        return row

    async def create_successor_revision(
        self,
        *,
        goal_id: str,
        expected_current_revision_id: str,
        created_by: str,
        plan: dict[str, Any],
        reason: str,
        status: str = "draft",
        rationale: str | None = None,
        trace_ref: str | None = None,
    ) -> dict[str, Any]:
        """Append revision N+1, diffed against the predecessor's stored plan.

        Raises :class:`StalePlanRevisionError` when ``expected_current_revision_id`` is no longer
        the goal's current revision, and :class:`PlanLineageError` when it does not exist or
        belongs to another goal. Neither is retried here.
        """
        if reason == "initial":
            raise PlanLineageError(
                "reason 'initial' is reserved for a root revision; a successor must name the "
                "cause that produced it"
            )
        content = parse_plan(plan)

        predecessor = await self.store.get_revision(expected_current_revision_id)
        if predecessor is None:
            raise PlanLineageError(f"unknown predecessor revision {expected_current_revision_id}")
        previous_content = parse_plan(predecessor["plan"])
        diff = compute_plan_diff(previous_content, content, rationale=rationale)

        try:
            row = await self.store.create_successor_revision(
                {
                    "goal_id": goal_id,
                    "expected_current_revision_id": expected_current_revision_id,
                    "created_by": created_by,
                    "plan": content.model_dump(mode="json"),
                    "diff": diff.model_dump(mode="json"),
                    "reason": reason,
                    "status": status,
                    "trace_ref": trace_ref,
                }
            )
        except StalePlanRevisionError as exc:
            await self._audit(
                planning_events.AUDIT_PLAN_REVISION_STALE_REJECTED,
                f"successor rejected for goal {goal_id}: expected revision "
                f"{exc.expected_revision_id} is no longer current",
                "rejected_stale",
                {
                    "goal_id": str(goal_id),
                    "expected_revision_id": exc.expected_revision_id or "",
                    "actual_revision_id": exc.actual_revision_id or "",
                    "created_by": str(created_by),
                },
            )
            raise

        await self._audit(
            planning_events.AUDIT_PLAN_REVISION_SUPERSEDED,
            f"plan revision {row['plan_revision_id']} supersedes "
            f"{row['supersedes_revision_id']} for goal {goal_id}",
            "recorded",
            {
                "plan_revision_id": str(row["plan_revision_id"]),
                "goal_id": str(row["goal_id"]),
                "revision_number": str(row["revision_number"]),
                "reason": row["reason"],
                "supersedes_revision_id": str(row["supersedes_revision_id"]),
                "created_by": str(row["created_by"]),
            },
        )
        return row

    async def accept_revision(self, plan_revision_id: str) -> dict[str, Any] | None:
        """Record team acceptance of a revision: ``draft -> accepted`` on the same row.

        This is the pipeline's ``plan acceptance`` stage (planning-and-plan-revision-model.md
        section 4), and the only status transition the approved architecture names. It writes
        nothing but the status: plan, diff and lineage stay exactly as authored, which is what
        "immutable once accepted" means in source-of-truth-and-lineage-model.md.

        Deliberately NOT implemented here: choosing WHICH revision the team accepts, and recording
        the TeamDecision that carries that choice. That orchestration is M3.4's, and the approved
        linkage it will use -- ``team_decisions.resulting_plan_revision_id`` -- already exists.
        This slice supplies only the primitive M3.4 needs to call.
        """
        row = await self.store.accept_revision(plan_revision_id)
        if row is None:
            return None
        await self._audit(
            planning_events.AUDIT_PLAN_REVISION_ACCEPTED,
            f"plan revision {row['plan_revision_id']} accepted for goal {row['goal_id']}",
            "accepted",
            {
                "plan_revision_id": str(row["plan_revision_id"]),
                "goal_id": str(row["goal_id"]),
                "revision_number": str(row["revision_number"]),
                "status": row["status"],
            },
        )
        return row

    # --- reads ---------------------------------------------------------------------------------

    async def get_current_revision(self, goal_id: str) -> dict[str, Any] | None:
        return await self.store.get_current_revision(goal_id)

    async def list_revisions(self, goal_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return await self.store.list_revisions(goal_id, limit=limit)

    async def get_diff(self, plan_revision_id: str) -> dict[str, Any] | None:
        """A revision's own structured change set from its predecessor.

        A root revision honestly returns an empty diff rather than ``None``: it exists and has no
        predecessor, which is different from "this revision is unknown".
        """
        row = await self.store.get_revision(plan_revision_id)
        if row is None:
            return None
        return {
            "plan_revision_id": str(row["plan_revision_id"]),
            "supersedes_revision_id": (
                str(row["supersedes_revision_id"]) if row["supersedes_revision_id"] else None
            ),
            "reason": row["reason"],
            "diff": row["diff"],
        }

    async def as_model(self, row: dict[str, Any]) -> PlanRevision:
        """A validated read view of a stored row, with ``is_current`` derived from lineage."""
        return PlanRevision(
            plan_revision_id=row["plan_revision_id"],
            project_id=row["project_id"],
            goal_id=row["goal_id"],
            revision_number=row["revision_number"],
            created_by=row["created_by"],
            reason=row["reason"],
            supersedes_revision_id=row["supersedes_revision_id"],
            status=row["status"],
            plan=PlanContent.model_validate(row["plan"]),
            diff=PlanDiff.model_validate(row["diff"] or {}),
            trace_ref=row.get("trace_ref"),
            audit_ref=row.get("audit_ref"),
            created_at=row.get("created_at"),
            is_current=await self.store.is_current(row["plan_revision_id"]),
        )

    @staticmethod
    def goal_model(row: dict[str, Any]) -> Goal:
        return Goal(
            goal_id=row["goal_id"],
            project_id=row["project_id"],
            statement=row["statement"],
            acceptance_criteria=tuple(row["acceptance_criteria"]),
            constraints=tuple(row["constraints"]),
            created_by=row["created_by"],
            status=row["status"],
            audit_ref=row.get("audit_ref"),
            created_at=row.get("created_at"),
        )


__all__ = ["PlanningService"]
