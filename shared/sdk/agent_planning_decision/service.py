"""Step AT-M3.4 -- the formal planning decision runtime.

One command: take a converged AT-M3.3 discussion and turn it into one TeamDecision and one accepted
PlanRevision. Everything else in this module is reading.

Four deliberate refusals:

* **No second decision entity.** The formal decision IS an AT-M2 ``TeamDecision``. The ledger row
  this slice adds records which discussion produced it; it decides nothing.
* **No Proposal or Challenge table.** The architecture's lineage matrix defines neither, and
  ``collaboration-and-workroom-model.md`` section 6 already makes propose/challenge durable as
  message types. The evidence read below surfaces them from where they already live.
* **No provider call.** AT-M3.3's convergence summary is a ``DecisionSummaryArtifact``, whose
  ``options_considered`` / ``selected_option`` / ``dissent_summary`` are exactly the three fields
  the TeamDecision contract names. The structured result already IS the decision evidence, so
  formalizing it is deterministic and no reasoning invocation happens here.
* **No execution.** No WorkItem, no dispatch, no routing, no tool, no test run, no deployment. M3.4
  ends at an accepted plan; acting on that plan is M3.5 and M4.

And one thing it is emphatically not: a ``TeamDecision`` is not a human Approval, does not satisfy
a production approval, and changes no authorization state (AT-ADR-06 / INV-03, AT-D14 section 4).
"""

from __future__ import annotations

from typing import Any

from shared.sdk.agent_deliberation.store import DeliberationStore
from shared.sdk.agent_planning.models import StalePlanRevisionError, compute_plan_diff
from shared.sdk.agent_planning.models import PlanContent
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_planning_decision import events as decision_events
from shared.sdk.agent_planning_decision.models import (
    DiscussionNotAdmissibleError,
    build_decision_evidence,
    derive_idempotency_key,
    evaluate_admissibility,
    validate_plan,
)
from shared.sdk.agent_planning_decision.store import LedgerRaceLost, PlanningDecisionStore
from shared.sdk.agent_team.store import TeamStore


class PlanningDecisionService:
    def __init__(
        self,
        store: Any | None = None,
        planning_store: Any | None = None,
        deliberation_store: Any | None = None,
        team_store: Any | None = None,
        audit_client: Any | None = None,
    ) -> None:
        self.store = store if store is not None else PlanningDecisionStore()
        self.planning = planning_store if planning_store is not None else PlanningStore()
        self.deliberation = (
            deliberation_store if deliberation_store is not None else DeliberationStore()
        )
        self.team = team_store if team_store is not None else TeamStore()
        self.audit_client = audit_client

    # --- audit ---------------------------------------------------------------------------------

    async def _audit(
        self, decision_type: str, summary: str, result: str, refs: dict[str, Any]
    ) -> str | None:
        """Best-effort, identifiers only. Never a message body, a plan or a rationale."""
        if self.audit_client is None:
            return None
        try:
            event = self.audit_client.build_audit_event(
                agent="planning-decision-runtime",
                decision_type=decision_type,
                summary=summary,
                result=result,
                artifact_refs=refs,
            )
            return await self.audit_client.write_audit_event(event)
        except Exception:
            return None

    # --- the one command -------------------------------------------------------------------------

    async def finalize(
        self,
        *,
        goal_id: str,
        discussion_id: str,
        decided_by: str,
        plan: Any,
    ) -> dict[str, Any]:
        """Formalize one converged discussion. Idempotent, safe to race, fail-closed when stale.

        Returns ``{"created": bool, "planning_decision": ..., "team_decision": ...,
        "plan_revision": ...}``. ``created=False`` means this discussion had already been
        formalized and the canonical result is being replayed -- an outcome, not an error, and the
        difference between "I did this" and "this was already done" is worth reporting honestly.

        The stale path and the raced path look identical from a naive caller's seat and are
        emphatically not the same thing, so they are separated by a single question asked after the
        failure: *did a ledger row appear for MY discussion?* If it did, another worker did this
        exact work and its result is canonical. If it did not, some other path moved the plan out
        from under this discussion, and the discussion is now historical evidence about a revision
        that is no longer current -- which is a refusal, not a retry.
        """
        existing = await self.store.get_by_discussion(discussion_id)
        if existing is not None:
            return await self._replay(existing, "already finalized")

        discussion = await self.deliberation.get_session(discussion_id)
        current = await self.planning.get_current_revision(goal_id)
        current_id = current["plan_revision_id"] if current else None

        verdict = evaluate_admissibility(
            discussion=discussion, goal_id=goal_id, current_plan_revision_id=current_id
        )
        if not verdict.admissible:
            await self._audit(
                decision_events.AUDIT_PLANNING_DECISION_REJECTED,
                f"discussion {discussion_id} refused as planning input",
                verdict.clause,
                {
                    "discussion_id": str(discussion_id),
                    "goal_id": str(goal_id),
                    "clause": verdict.clause,
                },
            )
            raise DiscussionNotAdmissibleError(discussion_id, verdict.clause, verdict.detail)

        assert discussion is not None  # evaluate_admissibility already refused None
        structured = validate_plan(plan)
        diff = self._diff_against(current, structured)
        messages = await self.team.list_messages(
            str(discussion["project_id"]), str(discussion["thread_id"])
        )
        turns = await self.deliberation.list_turns(discussion_id)
        result_message = next(
            (m for m in messages if str(m["message_id"]) == str(discussion["result_message_id"])),
            None,
        )
        if result_message is None:
            raise DiscussionNotAdmissibleError(
                discussion_id,
                "result",
                "the discussion names a result message that is not in its thread",
            )
        evidence = build_decision_evidence(
            result_message=result_message, messages=messages, turns=turns
        )

        try:
            written = await self.store.finalize(
                project_id=discussion["project_id"],
                goal_id=goal_id,
                discussion_id=discussion_id,
                thread_id=discussion["thread_id"],
                result_message_id=discussion["result_message_id"],
                predecessor_plan_revision_id=discussion["plan_revision_id"],
                decided_by=decided_by,
                plan=structured,
                diff=diff,
                evidence=evidence,
                idempotency_key=derive_idempotency_key(
                    discussion_id=discussion_id,
                    result_message_id=discussion["result_message_id"],
                ),
            )
        except LedgerRaceLost:
            settled = await self.store.get_by_discussion(discussion_id)
            if settled is None:  # pragma: no cover -- the ledger raced and then vanished
                raise
            return await self._replay(settled, "another worker finalized this discussion first")
        except StalePlanRevisionError:
            # The predecessor gained a successor between the pre-read and the write. If that
            # successor is OURS, we lost a race on the same discussion and the answer is its
            # result; if it is not, the plan moved on without us and we refuse.
            settled = await self.store.get_by_discussion(discussion_id)
            if settled is not None:
                return await self._replay(settled, "another worker finalized this discussion first")
            await self._audit(
                decision_events.AUDIT_PLANNING_DECISION_REJECTED,
                f"discussion {discussion_id} lost its predecessor before the decision was written",
                "currency",
                {
                    "discussion_id": str(discussion_id),
                    "goal_id": str(goal_id),
                    "predecessor_plan_revision_id": str(discussion["plan_revision_id"]),
                },
            )
            raise

        await self._audit(
            decision_events.AUDIT_PLANNING_DECISION_RECORDED,
            f"planning decision {written['planning_decision']['planning_decision_id']} recorded",
            written["planning_decision"]["outcome"],
            {
                "planning_decision_id": str(written["planning_decision"]["planning_decision_id"]),
                "goal_id": str(goal_id),
                "discussion_id": str(discussion_id),
                "result_message_id": str(discussion["result_message_id"]),
                "predecessor_plan_revision_id": (
                    str(discussion["plan_revision_id"]) if discussion["plan_revision_id"] else None
                ),
                "team_decision_id": str(written["team_decision"]["decision_id"]),
                "resulting_plan_revision_id": str(written["plan_revision"]["plan_revision_id"]),
                "revision_status": written["plan_revision"]["status"],
                "decided_by": str(decided_by),
                "proposal_message_ids": list(evidence.proposal_message_ids),
                "challenge_message_ids": list(evidence.challenge_message_ids),
            },
        )
        return {"created": True, "detail": "planning decision recorded", **written}

    async def _replay(self, ledger: dict[str, Any], detail: str) -> dict[str, Any]:
        """Return the canonical result of a finalization that already happened. Writes nothing."""
        await self._audit(
            decision_events.AUDIT_PLANNING_DECISION_REPLAYED,
            f"planning decision {ledger['planning_decision_id']} replayed",
            ledger["outcome"],
            {
                "planning_decision_id": str(ledger["planning_decision_id"]),
                "discussion_id": str(ledger["discussion_id"]),
                "team_decision_id": str(ledger["team_decision_id"]),
                "resulting_plan_revision_id": str(ledger["resulting_plan_revision_id"]),
            },
        )
        return {
            "created": False,
            "detail": detail,
            "planning_decision": ledger,
            "team_decision": await self.store.get_team_decision(ledger["team_decision_id"]),
            "plan_revision": await self.planning.get_revision(ledger["resulting_plan_revision_id"]),
        }

    @staticmethod
    def _diff_against(predecessor: dict[str, Any] | None, plan: dict[str, Any]) -> dict[str, Any]:
        """The structured diff, computed on the server from both plans.

        Never supplied by the caller: a diff a caller can assert is a diff that can lie about what
        changed. Reuses AT-M3.2's ``compute_plan_diff``, so a decision's diff means exactly what a
        revision comparison means everywhere else.

        A predecessor whose stored plan does not parse as ``PlanContent`` yields an empty diff
        rather than an exception. ``PlanningStore`` accepts a plan as raw JSON -- only
        ``PlanningService`` validates it -- so a revision written directly through the store can
        hold a shape this comparison cannot read. The diff is derived, advisory metadata; the plan
        itself is the truth. Losing the comparison costs a reviewer one convenience, whereas
        refusing would strand the Goal's whole lineage on the shape of one historical row, and that
        row is immutable by design. The empty diff is not a claim that nothing changed: a root
        revision is distinguishable by ``supersedes_revision_id``, and this case by the
        predecessor's own plan failing to parse.
        """
        if predecessor is None:
            return {}
        try:
            before = PlanContent(**(predecessor.get("plan") or {}))
        except Exception:
            return {}
        return compute_plan_diff(before, PlanContent(**plan)).model_dump(mode="json")

    # --- reads -------------------------------------------------------------------------------------

    async def get(self, planning_decision_id: str) -> dict[str, Any] | None:
        ledger = await self.store.get(planning_decision_id)
        if ledger is None:
            return None
        return await self._assemble(ledger)

    async def get_by_discussion(self, discussion_id: str) -> dict[str, Any] | None:
        ledger = await self.store.get_by_discussion(discussion_id)
        if ledger is None:
            return None
        return await self._assemble(ledger)

    async def list_for_goal(self, goal_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return await self.store.list_for_goal(goal_id, limit=limit)

    async def _assemble(self, ledger: dict[str, Any]) -> dict[str, Any]:
        return {
            "planning_decision": ledger,
            "team_decision": await self.store.get_team_decision(ledger["team_decision_id"]),
            "plan_revision": await self.planning.get_revision(ledger["resulting_plan_revision_id"]),
        }

    async def get_evidence(self, planning_decision_id: str) -> dict[str, Any] | None:
        """The deliberation the decision was formed from, from where it already lives.

        There is no Proposal table and no Challenge table to read, because the architecture defines
        neither. What a reviewer actually wants -- what was proposed, what was objected to, and
        which turn produced each -- is the thread's own messages joined to AT-M3.3's turn ledger,
        which is exactly what this returns. Reconstructing the lineage from here reaches
        Goal -> Discussion -> TeamMessages -> TeamDecision -> PlanRevision without a second record
        of any of them.
        """
        ledger = await self.store.get(planning_decision_id)
        if ledger is None:
            return None
        discussion = await self.deliberation.get_session(ledger["discussion_id"])
        if discussion is None:  # pragma: no cover -- FK-protected
            return None
        messages = await self.team.list_messages(
            str(discussion["project_id"]), str(discussion["thread_id"])
        )
        turns = await self.deliberation.list_turns(ledger["discussion_id"])
        intent_for_message = {
            str(t["message_id"]): t["intent"] for t in turns if t.get("message_id")
        }
        return {
            "planning_decision_id": str(ledger["planning_decision_id"]),
            "discussion_id": str(ledger["discussion_id"]),
            "goal_id": str(ledger["goal_id"]),
            "result_message_id": str(ledger["result_message_id"]),
            "proposals": [
                self._evidence_view(m, intent_for_message)
                for m in messages
                if m["message_type"] == "proposal"
            ],
            "challenges": [
                self._evidence_view(m, intent_for_message)
                for m in messages
                if m["message_type"] == "challenge"
            ],
        }

    @staticmethod
    def _evidence_view(
        message: dict[str, Any], intent_for_message: dict[str, str]
    ) -> dict[str, Any]:
        return {
            "message_id": str(message["message_id"]),
            "sender_principal_id": str(message["sender_principal_id"]),
            "message_type": message["message_type"],
            "discussion_intent": intent_for_message.get(str(message["message_id"])),
            "summary": message["summary"],
            "created_at": message.get("created_at"),
        }


__all__ = ["PlanningDecisionService"]
