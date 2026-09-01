"""Step AT-M3.4 -- the formal planning decision runtime.

One command: take a converged AT-M3.3 discussion, have the team's planner author a structured
candidate plan from it, and turn the two into one TeamDecision and -- when the plan actually
changes -- one accepted PlanRevision. Everything else in this module is reading.

Five deliberate refusals:

* **No caller-supplied plan.** AT-M3.4 Validation 1 handed this slice a plan reading "REWRITE
  EVERYTHING IN RUST" against a discussion that had selected something else, and it was recorded as
  what the team chose; with two callers racing, commit ordering decided which plan won. The fix is
  not a check -- it is removing the input. ``finalize`` takes two identifiers and nothing else, and
  the plan is read back from the planner's own durable message. There is nothing left to
  substitute.
* **No caller-supplied author, and no substitute one either.** The planner is the seated
  participant of THIS discussion whose matched capabilities include ``plan_project``, and that
  principal -- the one that was in the room and actually did the reasoning -- is who the
  TeamDecision and the PlanRevision are attributed to. A transport caller is not an author, and
  neither is a project member who joined after the room had already converged: routing one in
  after the fact would attribute a plan to somebody who never argued for it.
* **No second decision entity.** The formal decision IS an AT-M2 ``TeamDecision``. The ledger row
  this slice adds records which discussion produced it and which candidate plan it selected; it
  decides nothing.
* **No Proposal or Challenge table.** The architecture's lineage matrix defines neither, and
  ``collaboration-and-workroom-model.md`` section 6 already makes propose/challenge durable as
  message types. The candidate plan is stored the same way, and the evidence read below surfaces
  all of it from where it already lives.
* **No execution.** No WorkItem, no dispatch, no routing of work, no tool, no test run, no
  deployment. M3.4 ends at a decided plan; acting on it is M3.5 and M4.

And one thing it is emphatically not: a ``TeamDecision`` is not a human Approval, does not satisfy
a production approval, and changes no authorization state (AT-ADR-06 / INV-03, AT-D14 section 4).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from shared.sdk.agent_deliberation.store import DeliberationStore
from shared.sdk.agent_planning.models import (
    PlanContent,
    PlanLineageError,
    StalePlanRevisionError,
    compute_plan_diff,
)
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_planning_decision import events as decision_events
from shared.sdk.agent_planning_decision.models import (
    CANDIDATE_REF_KEY,
    CASE_CHANGED,
    CHALLENGE_MESSAGE_TYPE,
    OUTCOME_FOR_CASE,
    PLANNER_CAPABILITY,
    PLANNER_VERB,
    PROPOSAL_MESSAGE_TYPE,
    DiscussionNotAdmissibleError,
    PlannerUnavailableError,
    PlanningDecisionConflictError,
    PlanningDecisionStateError,
    build_decision_evidence,
    derive_candidate_correlation_id,
    derive_case,
    derive_idempotency_key,
    evaluate_admissibility,
    is_candidate_for,
    plan_from_candidate,
)
from shared.sdk.agent_planning_decision.store import (
    LedgerRaceLost,
    PlanningDecisionStore,
    RevisionAlreadyDecided,
)
from shared.sdk.agent_reasoning.models import ReasoningRequest
from shared.sdk.agent_reasoning.service import ReasoningService
from shared.sdk.agent_team.store import TeamStore

#: How much of the deliberation the planner is shown. Bounded on purpose: the planner needs what
#: the room concluded and what it argued about, not the database.
_EVIDENCE_LIMIT = 10


class PlanningDecisionService:
    def __init__(
        self,
        store: Any | None = None,
        planning_store: Any | None = None,
        deliberation_store: Any | None = None,
        team_store: Any | None = None,
        reasoning_service: Any | None = None,
        provider: Any | None = None,
        audit_client: Any | None = None,
    ) -> None:
        self.store = store if store is not None else PlanningDecisionStore()
        self.planning = planning_store if planning_store is not None else PlanningStore()
        self.deliberation = (
            deliberation_store if deliberation_store is not None else DeliberationStore()
        )
        self.team = team_store if team_store is not None else TeamStore()
        self.reasoning = reasoning_service if reasoning_service is not None else ReasoningService()
        self.provider = provider
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

    async def finalize(self, *, goal_id: str, discussion_id: str) -> dict[str, Any]:
        """Formalize one converged discussion. Idempotent, safe to race, fail-closed when stale.

        Two identifiers in. No plan, no principal, no outcome: all three are determined here from
        durable rows, which is what makes the result a record of what the team decided rather than
        of what a caller asserted.

        Returns ``{"created": bool, "outcome": str, "candidate_plan_message_id": ...,
        "planning_decision": ..., "team_decision": ..., "plan_revision": ...}``. ``created=False``
        means this discussion had already been formalized and the canonical result is being
        replayed -- an outcome, not an error, and the difference between "I did this" and "this was
        already done" is worth reporting honestly. ``plan_revision`` is ``None`` exactly when the
        outcome is ``no_change``.

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
        goal = await self.planning.get_goal(goal_id)
        messages = await self.team.list_messages(
            str(discussion["project_id"]), str(discussion["thread_id"])
        )
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

        planner = await self._resolve_planner(discussion)
        candidate = await self._ensure_candidate(
            discussion=discussion,
            goal=goal,
            current=current,
            planner=planner,
            messages=messages,
            result_message=result_message,
        )
        if candidate is None:
            settled = await self.store.get_by_discussion(discussion_id)
            if settled is None:  # pragma: no cover -- a ledger row that appeared and then vanished
                raise PlanningDecisionConflictError(
                    f"discussion {discussion_id} was finalized by another worker whose decision is "
                    "no longer readable"
                )
            return await self._replay(settled, "another worker finalized this discussion first")

        plan = plan_from_candidate(candidate)
        case = derive_case(current_revision=current, candidate_plan=plan)
        diff = self._diff_against(current, plan) if case == CASE_CHANGED else {}

        turns = await self.deliberation.list_turns(discussion_id)
        evidence = build_decision_evidence(
            result_message=result_message,
            messages=messages,
            turns=turns,
            discussion_id=discussion_id,
        )

        try:
            written = await self.store.finalize(
                case=case,
                project_id=discussion["project_id"],
                goal_id=goal_id,
                discussion_id=discussion_id,
                thread_id=discussion["thread_id"],
                result_message_id=discussion["result_message_id"],
                candidate_plan_message_id=candidate["message_id"],
                predecessor_plan_revision_id=discussion["plan_revision_id"],
                planner_principal_id=planner["principal_id"],
                plan=plan,
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
        except (StalePlanRevisionError, PlanLineageError, RevisionAlreadyDecided) as exc:
            # The ground moved between the pre-read and the write. If it moved because ANOTHER
            # worker finalized THIS discussion, the answer is that worker's result -- and the root
            # path reaches this through PlanLineageError ("goal already has an initial revision")
            # rather than StalePlanRevisionError, which is the AT-M3.4 Validation 1 defect that
            # left seven concurrent root-path workers holding a lineage error instead of the
            # canonical decision. If no decision exists for this discussion, some other path
            # genuinely moved the plan, and we refuse.
            settled = await self.store.get_by_discussion(discussion_id)
            if settled is not None:
                return await self._replay(settled, "another worker finalized this discussion first")
            await self._audit(
                decision_events.AUDIT_PLANNING_DECISION_REJECTED,
                f"discussion {discussion_id} lost its plan before the decision was written",
                "currency",
                {
                    "discussion_id": str(discussion_id),
                    "goal_id": str(goal_id),
                    "predecessor_plan_revision_id": (
                        str(discussion["plan_revision_id"])
                        if discussion["plan_revision_id"]
                        else None
                    ),
                },
            )
            if isinstance(exc, RevisionAlreadyDecided):
                raise PlanningDecisionConflictError(str(exc)) from exc
            raise

        revision = written.get("plan_revision")
        await self._audit(
            decision_events.AUDIT_PLANNING_DECISION_RECORDED,
            f"planning decision {written['planning_decision']['planning_decision_id']} recorded",
            written["planning_decision"]["outcome"],
            {
                "planning_decision_id": str(written["planning_decision"]["planning_decision_id"]),
                "goal_id": str(goal_id),
                "discussion_id": str(discussion_id),
                "result_message_id": str(discussion["result_message_id"]),
                "candidate_plan_message_id": str(candidate["message_id"]),
                "planner_principal_id": str(planner["principal_id"]),
                "planner_source": planner["source"],
                "predecessor_plan_revision_id": (
                    str(discussion["plan_revision_id"]) if discussion["plan_revision_id"] else None
                ),
                "team_decision_id": str(written["team_decision"]["decision_id"]),
                "resulting_plan_revision_id": (
                    str(revision["plan_revision_id"]) if revision else None
                ),
                "revision_status": revision["status"] if revision else None,
                "outcome": written["planning_decision"]["outcome"],
                "proposal_message_ids": list(evidence.proposal_message_ids),
                "challenge_message_ids": list(evidence.challenge_message_ids),
            },
        )
        return {
            "created": True,
            "detail": f"planning decision recorded ({OUTCOME_FOR_CASE[case]})",
            "outcome": written["planning_decision"]["outcome"],
            "candidate_plan_message_id": str(candidate["message_id"]),
            **written,
        }

    # --- the planner -----------------------------------------------------------------------------

    async def _resolve_planner(self, discussion: dict[str, Any]) -> dict[str, Any]:
        """Who authors the plan. Read from THIS discussion's own roster, never named by a caller.

        The rule, and it has no second branch:

            the planner MUST be a seated participant of this exact discussion whose stored
            ``matched_capabilities`` include ``plan_project``.

        The earlier implementation fell back to the AT-M2 capability router over current project
        membership when no seated planner existed. That fallback is removed, because what it
        produced was a false attribution: it routed a principal who was never in the room into an
        already-converged discussion and recorded them as the author of the plan that discussion
        selected. Nobody could later tell that apart from a plan its author had actually argued
        for, which is the same class of defect as accepting ``decided_by`` from the request.

        Deterministic when several qualify: lowest ``seat_index`` wins. Arbitrary among equals, but
        arbitrary the SAME way every time, so a replay attributes the plan to the same principal.

        Capabilities are read as the router matched them AT OPEN TIME, not re-derived now. A
        discussion is a record of who was in the room; re-deriving membership at decision time
        would let a roster change rewrite the authorship of a decision already reached.

        Fail closed if nobody qualifies. A discussion with no planner in it did not produce a plan,
        and saying so is the honest outcome -- a plan attributed to a principal that did not author
        it is worse than no plan.
        """
        participants = await self.deliberation.list_participants(str(discussion["discussion_id"]))
        seated = [
            participant
            for participant in sorted(participants, key=lambda p: p.get("seat_index") or 0)
            if PLANNER_CAPABILITY in list(participant.get("matched_capabilities") or [])
        ]
        if not seated:
            raise PlannerUnavailableError(
                f"discussion {discussion['discussion_id']} seated no participant with the "
                f"{PLANNER_CAPABILITY!r} capability, so it has no author for a plan. A discussion "
                "intended to produce a planning decision must require that capability when it is "
                "opened; a principal who was not in the room is not an alternative."
            )
        return {
            "principal_id": str(seated[0]["principal_id"]),
            "agent_key": seated[0].get("agent_key"),
            "seat_index": seated[0].get("seat_index"),
            "source": "discussion_participant",
        }

    async def _ensure_candidate(
        self,
        *,
        discussion: dict[str, Any],
        goal: dict[str, Any] | None,
        current: dict[str, Any] | None,
        planner: dict[str, Any],
        messages: list[dict[str, Any]],
        result_message: dict[str, Any],
    ) -> dict[str, Any] | None:
        """The one candidate plan for this discussion: found, or authored now.

        Returns ``None`` when the discussion turns out to have been finalized already, which the
        caller resolves into a replay.

        **The reasoning call happens outside every lock and every transaction.** The earlier
        implementation held the discussion row locked across it, because a worker that lost the
        race had no way to obtain the artifact and had to wait for the winner to write the message.
        That is no longer true: AT-M3.1 now stores the artifact durably, so every worker can
        recover the same plan independently, and the lock shrank to what it always should have
        been -- the message INSERT. It is also what makes this shape safe for a live provider,
        where holding a database lock across a network call would not be.

        What still makes "one candidate per discussion" true under concurrency, without a polling
        loop and without a lock registry:

        * ``uq_reasoning_invocations_correlation`` -- the correlation id is derived from the
          discussion, so one ``decompose_plan`` invocation exists per discussion as a database
          fact, and every other worker replays its artifact rather than making a second call;
        * the discussion row lock around the INSERT -- eight workers holding the same recovered
          artifact queue on the row they are all consuming, the first writes the message, and the
          other seven find it already written.

        The candidate is written in ITS OWN transaction, not the decision's. A finalization that
        later goes stale still leaves the plan the planner drafted, as durable evidence that it was
        drafted and not adopted -- the same posture ``planning-and-plan-revision-model.md`` section
        11e takes toward a stale discussion.
        """
        discussion_id = str(discussion["discussion_id"])
        existing = next((m for m in messages if is_candidate_for(m, discussion_id)), None)
        if existing is not None:
            return existing

        authored = await self._author_plan(
            discussion=discussion,
            goal=goal,
            current=current,
            planner=planner,
            messages=messages,
            result_message=result_message,
        )
        artifact = authored["artifact"]

        conn = await self.store._connect()
        try:
            async with conn.transaction():
                await conn.fetchval(
                    "SELECT discussion_id FROM discussion_sessions WHERE discussion_id=$1 "
                    "FOR UPDATE",
                    uuid.UUID(discussion_id),
                )
                if await conn.fetchval(
                    "SELECT 1 FROM planning_decisions WHERE discussion_id=$1",
                    uuid.UUID(discussion_id),
                ):
                    return None

                for row in await conn.fetch(
                    "SELECT * FROM team_messages WHERE thread_id=$1 AND message_type=$2",
                    uuid.UUID(str(discussion["thread_id"])),
                    PROPOSAL_MESSAGE_TYPE,
                ):
                    message = self._decoded(dict(row))
                    if is_candidate_for(message, discussion_id):
                        return message

                return await self.team.post_message(
                    {
                        "thread_id": str(discussion["thread_id"]),
                        "project_id": str(discussion["project_id"]),
                        "sender_principal_id": planner["principal_id"],
                        "recipient_team": True,
                        "parent_message_id": str(discussion["result_message_id"]),
                        "message_type": PROPOSAL_MESSAGE_TYPE,
                        "summary": artifact.summary[:2000],
                        "content": artifact.as_safe_dict(),
                        "artifact_refs": {
                            CANDIDATE_REF_KEY: discussion_id,
                            "goal_id": str(discussion["goal_id"]),
                            "result_message_id": str(discussion["result_message_id"]),
                            "plan_revision_id": (
                                str(discussion["plan_revision_id"])
                                if discussion["plan_revision_id"]
                                else None
                            ),
                            "reasoning_invocation_id": str(authored["invocation_id"]),
                            "reasoning_attempt": authored["attempt"],
                        },
                    },
                    conn=conn,
                )
        finally:
            await conn.close()

    async def _author_plan(
        self,
        *,
        discussion: dict[str, Any],
        goal: dict[str, Any] | None,
        current: dict[str, Any] | None,
        planner: dict[str, Any],
        messages: list[dict[str, Any]],
        result_message: dict[str, Any],
    ) -> dict[str, Any]:
        """One ``decompose_plan`` call, on approved durable context only.

        What the planner is shown is bounded and named field by field: the Goal it serves, what the
        room concluded, a capped sample of what was proposed and objected to, and the plan the Goal
        currently has. No thread dump, no unrelated database state, no other project.
        """
        content = result_message.get("content") or {}
        if not isinstance(content, dict):
            content = {}
        deliberation = [
            m for m in messages if not is_candidate_for(m, str(discussion["discussion_id"]))
        ]

        context: dict[str, Any] = {
            "goal_statement": (goal or {}).get("statement"),
            "acceptance_criteria": list((goal or {}).get("acceptance_criteria") or []),
            "goal_constraints": list((goal or {}).get("constraints") or []),
            "selected_option": content.get("selected_option"),
            "options_considered": list(content.get("options_considered") or []),
            "dissent_summary": content.get("dissent_summary"),
            "proposal_summaries": [
                m.get("summary")
                for m in deliberation
                if m.get("message_type") == PROPOSAL_MESSAGE_TYPE
            ][:_EVIDENCE_LIMIT],
            "challenge_summaries": [
                m.get("summary")
                for m in deliberation
                if m.get("message_type") == CHALLENGE_MESSAGE_TYPE
            ][:_EVIDENCE_LIMIT],
            "current_plan": (current or {}).get("plan"),
        }

        result = await self.reasoning.invoke(
            ReasoningRequest(
                verb=PLANNER_VERB,  # type: ignore[arg-type]
                context=context,
                project_id=str(discussion["project_id"]),
                thread_id=str(discussion["thread_id"]),
                requested_by_principal_id=planner["principal_id"],
                correlation_id=derive_candidate_correlation_id(
                    discussion_id=discussion["discussion_id"],
                    result_message_id=discussion["result_message_id"],
                ),
            ),
            provider=self.provider,
        )
        if result.artifact is not None:
            # Either this call produced it (`fresh`) or it was recovered from the durable
            # invocation (`replay`). Both are the planner's own plan for this discussion, and the
            # difference matters for attempt accounting, not for what the plan IS. Accepting only
            # `fresh` here is what turned a crash between the reasoning commit and the message
            # write into a permanent strand -- the artifact was already durable and this branch
            # refused to look at it.
            return {
                "artifact": result.artifact,
                "invocation_id": result.invocation["invocation_id"],
                "attempt": result.invocation.get("attempt", 1),
            }

        if result.disposition == "in_progress":
            # Another worker holds a LIVE lease on this discussion's one reasoning call. Bounded,
            # not indefinite: the lease expires and a later retry takes the attempt over. Retryable
            # by the caller, so it is a conflict rather than a refusal.
            raise PlanningDecisionConflictError(
                f"the plan for discussion {discussion['discussion_id']} is being authored by "
                f"another worker (attempt {result.invocation.get('attempt')}); retry"
            )

        # Terminal, and it produced nothing. Fail closed and say which kind of failure it was. A
        # refused or unavailable provider never yields a substitute plan -- that is AT-D14 section
        # 4's first safety invariant, and a fabricated plan would be exactly the substitution this
        # milestone removed.
        raise PlanningDecisionStateError(
            "the planner produced no candidate plan for discussion "
            f"{discussion['discussion_id']} (reasoning {result.invocation.get('status')}"
            f"/{result.invocation.get('failure_category')}, "
            f"disposition {result.disposition})"
        )

    async def _replay(self, ledger: dict[str, Any], detail: str) -> dict[str, Any]:
        """Return the canonical result of a finalization that already happened. Writes nothing."""
        await self._audit(
            decision_events.AUDIT_PLANNING_DECISION_REPLAYED,
            f"planning decision {ledger['planning_decision_id']} replayed",
            ledger["outcome"],
            {
                "planning_decision_id": str(ledger["planning_decision_id"]),
                "discussion_id": str(ledger["discussion_id"]),
                "candidate_plan_message_id": str(ledger["candidate_plan_message_id"]),
                "team_decision_id": str(ledger["team_decision_id"]),
                "resulting_plan_revision_id": (
                    str(ledger["resulting_plan_revision_id"])
                    if ledger["resulting_plan_revision_id"]
                    else None
                ),
            },
        )
        return {
            "created": False,
            "detail": detail,
            "outcome": ledger["outcome"],
            "candidate_plan_message_id": str(ledger["candidate_plan_message_id"]),
            "planning_decision": ledger,
            "team_decision": await self.store.get_team_decision(ledger["team_decision_id"]),
            "plan_revision": (
                await self.planning.get_revision(ledger["resulting_plan_revision_id"])
                if ledger["resulting_plan_revision_id"]
                else None
            ),
        }

    @staticmethod
    def _decoded(row: dict[str, Any]) -> dict[str, Any]:
        """asyncpg returns JSONB as text unless a codec is registered."""
        for key in ("content", "artifact_refs"):
            if isinstance(row.get(key), str):
                row[key] = json.loads(row[key])
        return row

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
        row is immutable by design. It is never mistakable for "nothing changed": this is only
        called for the changed-plan case, and a no-change decision writes no revision at all.
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
            "plan_revision": (
                await self.planning.get_revision(ledger["resulting_plan_revision_id"])
                if ledger["resulting_plan_revision_id"]
                else None
            ),
        }

    async def get_evidence(self, planning_decision_id: str) -> dict[str, Any] | None:
        """The deliberation and the plan the decision was formed from, from where they already live.

        There is no Proposal table and no Challenge table to read, because the architecture defines
        neither. What a reviewer actually wants -- what was proposed, what was objected to, which
        turn produced each, and the exact structured plan the decision selected -- is the thread's
        own messages joined to AT-M3.3's turn ledger, which is what this returns. Reconstructing
        the lineage from here reaches Goal -> Discussion -> TeamMessages -> candidate plan ->
        TeamDecision -> PlanRevision without a second record of any of them.

        The candidate is read by the id the ledger names and then checked to belong to this exact
        discussion, thread and Goal. A proposal from anywhere else cannot appear in its place.
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

        candidate = await self.store.get_message(ledger["candidate_plan_message_id"])
        if candidate is not None and not (
            is_candidate_for(candidate, str(ledger["discussion_id"]))
            and str(candidate["thread_id"]) == str(discussion["thread_id"])
            and str((candidate.get("artifact_refs") or {}).get("goal_id")) == str(ledger["goal_id"])
        ):  # pragma: no cover -- the write path and the FK make this unreachable
            candidate = None

        deliberation = [
            m for m in messages if not is_candidate_for(m, str(ledger["discussion_id"]))
        ]
        result_message = next(
            (m for m in messages if str(m["message_id"]) == str(ledger["result_message_id"])),
            None,
        )
        return {
            "planning_decision_id": str(ledger["planning_decision_id"]),
            "discussion_id": str(ledger["discussion_id"]),
            "goal_id": str(ledger["goal_id"]),
            "outcome": ledger["outcome"],
            "result_message_id": str(ledger["result_message_id"]),
            "convergence_result": (
                self._evidence_view(result_message, intent_for_message) if result_message else None
            ),
            "candidate_plan": (
                {
                    **self._evidence_view(candidate, intent_for_message),
                    "planner_principal_id": str(candidate["sender_principal_id"]),
                    "plan": (candidate.get("content") or {}).get("plan"),
                    "reasoning_invocation_id": (
                        (candidate.get("artifact_refs") or {}).get("reasoning_invocation_id")
                    ),
                }
                if candidate
                else None
            ),
            "proposals": [
                self._evidence_view(m, intent_for_message)
                for m in deliberation
                if m["message_type"] == PROPOSAL_MESSAGE_TYPE
            ],
            "challenges": [
                self._evidence_view(m, intent_for_message)
                for m in deliberation
                if m["message_type"] == CHALLENGE_MESSAGE_TYPE
            ],
            "team_decision_id": str(ledger["team_decision_id"]),
            "resulting_plan_revision_id": (
                str(ledger["resulting_plan_revision_id"])
                if ledger["resulting_plan_revision_id"]
                else None
            ),
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
