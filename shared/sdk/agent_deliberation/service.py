"""Step AT-M3.3 -- the bounded team discussion runtime.

Composes what already exists rather than adding a parallel stack: Goals and PlanRevisions come
from AT-M3.2, participants from the AT-M2 team and its capability router, the conversation from
``ConversationThread``/``TeamMessage``, and every reasoning call from AT-M3.1. What this module
adds is the bounded orchestration those pieces have nowhere to live in.

Four deliberate refusals:

* **No decision is ever recorded.** M3.3 produces a discussion and a durable summary of where it
  got to. Choosing an option, writing a ``TeamDecision``, accepting or rejecting a PlanRevision,
  creating a successor revision, decomposing work or dispatching anything are all M3.4/M3.5, and
  nothing here writes any of them. ``resulting_plan_revision_id`` is never touched.
* **No provider is called directly.** Every reasoning turn goes through ``ReasoningService``, so
  the durable invocation metadata, the fail-closed refusal behaviour and the no-hidden-reasoning
  guarantees AT-M3.1 already proved apply unchanged. A refused provider raises; it is never
  downgraded into a mock-authored message.
* **No turn is invented.** If the provider fails, the discussion stops with
  ``reasoning_provider_failure``. It does not substitute a placeholder reply, because a fabricated
  message is indistinguishable from a real one once it is in the thread.
* **Nothing decides the next turn from memory.** Every step reads the durable ledger, which is
  what makes the runtime resumable across processes.
* **The plan binding never moves.** A discussion is permanently about the exact PlanRevision it
  opened against. A legitimate successor appearing mid-flight does not terminate it, mutate it or
  rebind it, and produces no stale state and no stale flag; currency is derived at read time from
  AT-M3.2's lineage. Per AT-M3.3-PLAN-STALENESS-DESIGN-REVIEW-1, the boundary that protects the
  plan is M3.2's compare-and-swap when a successor is written, not a poll on every turn here.

Five bounds end a discussion: rounds, messages, invocations, per-participant turns and elapsed
time. Only the last can end one that nobody is advancing, which is why it exists -- and it is
checked at four points, not one: before a slot is claimed, when a slot someone else holds is
encountered, before a reasoning result becomes a TeamMessage, and at the round boundary. The
third is the one that matters most: a provider call is the only step that takes real time, so it
is the step during which the deadline realistically passes.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.agent_deliberation import events as discussion_events
from shared.sdk.agent_deliberation.models import (
    MESSAGE_TYPE_FOR_INTENT,
    MIN_PARTICIPANTS,
    DiscussionBounds,
    DiscussionParticipantError,
    DiscussionStateError,
    build_turn_context,
    classify_intent,
    derive_correlation_id,
    derive_idempotency_key,
    evaluate_convergence,
    plan_turn,
    summary_seat,
)
from shared.sdk.agent_deliberation.store import DeliberationStore
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_reasoning.models import ReasoningRequest
from shared.sdk.agent_reasoning.service import ReasoningService
from shared.sdk.agent_team.router import RoutingRequest, route
from shared.sdk.agent_team.store import TeamStore

#: A provisional label written when a slot is claimed, before the artifact exists to classify it.
#: Replaced by the real intent when the turn is recorded; the DB CHECK requires a valid value from
#: the moment the row exists, and "the verb's default meaning" is the honest placeholder.
_PROVISIONAL_INTENT = {
    "propose": "proposal",
    "critique": "challenge",
    "summarize_decision": "convergence_summary",
}

#: Closures that are NOT subject to the deadline-precedence guard in :meth:`DiscussionService._close`.
#:
#: ``timeout_reached`` is the reason the guard exists to protect, so guarding it against itself
#: would be circular. ``cancelled`` is an explicit act by whoever opened the discussion rather than
#: a bound firing, and an operator who cancels a discussion should get ``cancelled`` recorded even
#: if the wall clock happened to run out first -- what they did is what the record should say.
_UNGUARDED_CLOSE_REASONS = frozenset({"cancelled", "timeout_reached"})


class DiscussionService:
    def __init__(
        self,
        store: Any | None = None,
        team_store: Any | None = None,
        planning_store: Any | None = None,
        reasoning: Any | None = None,
        audit_client: Any | None = None,
        provider: Any | None = None,
    ) -> None:
        self.store = store if store is not None else DeliberationStore()
        self.team_store = team_store if team_store is not None else TeamStore()
        self.planning_store = planning_store if planning_store is not None else PlanningStore()
        self.reasoning = reasoning if reasoning is not None else ReasoningService()
        self.audit_client = audit_client
        # Injected only so a test can supply a deterministic provider. When None, AT-M3.1's own
        # factory resolves it -- which in this slice means the mock provider or a refusal, never a
        # network call.
        self.provider = provider

    # --- audit ---------------------------------------------------------------------------------

    async def _audit(
        self, decision_type: str, summary: str, result: str, refs: dict[str, Any]
    ) -> str | None:
        """Best-effort, identifiers only. Never a message body, a plan or a rationale."""
        if self.audit_client is None:
            return None
        try:
            event = self.audit_client.build_audit_event(
                agent="discussion-runtime",
                decision_type=decision_type,
                summary=summary,
                result=result,
                artifact_refs=refs,
            )
            return await self.audit_client.write_audit_event(event)
        except Exception:
            return None

    # --- participant selection -----------------------------------------------------------------

    async def select_participants(
        self, project_id: str, required_capabilities: tuple[str, ...]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Who should be in the room, using the existing team and the existing router.

        One routing decision per required capability, against the project's CURRENT membership.
        No second agent registry and no second selection rule: the same router that decides who
        takes a work item decides who is asked about one, so a team change moves both together.

        Returns ``(participants, uncovered)``. An agent that wins two capabilities keeps one seat
        and both capabilities -- a duplicate participant is not de-duplicated after the fact, it is
        never created.
        """
        candidates = await self.team_store.routing_candidates(project_id)
        by_principal: dict[str, dict[str, Any]] = {}
        uncovered: list[dict[str, Any]] = []

        for capability in required_capabilities:
            decision = route(
                RoutingRequest(requested_capability=capability, project_id=project_id), candidates
            )
            if not decision.selected or decision.selected_principal_id is None:
                uncovered.append(
                    {
                        "capability": capability,
                        "outcome": decision.outcome,
                        "reason": decision.reason,
                    }
                )
                continue
            existing = by_principal.get(decision.selected_principal_id)
            if existing is not None:
                existing["matched_capabilities"] = tuple(
                    dict.fromkeys((*existing["matched_capabilities"], capability))
                )
                continue
            by_principal[decision.selected_principal_id] = {
                "principal_id": decision.selected_principal_id,
                "agent_key": decision.selected_agent_key,
                "functional_role": decision.selected_role,
                "matched_capabilities": (capability,),
                "selection_reason": decision.reason[:1000],
            }

        participants = list(by_principal.values())
        # Deterministic seating: the router's own ranking already broke ties by agent_key, so
        # ordering by it here means the same team and the same request always seat the same way.
        participants.sort(key=lambda p: p["agent_key"])
        for seat, participant in enumerate(participants):
            participant["seat_index"] = seat
        return participants, uncovered

    # --- lifecycle -----------------------------------------------------------------------------

    async def start_discussion(
        self,
        *,
        project_id: str,
        goal_id: str,
        topic: str,
        opened_by: str,
        required_capabilities: tuple[str, ...],
        plan_revision_id: str | None = None,
        bounds: DiscussionBounds | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Open one bounded deliberation about a Goal and the plan it currently has.

        Fails CLOSED and durably: when the team cannot cover the required capabilities, the
        discussion is still recorded -- terminal, with ``insufficient_capability_coverage`` -- so
        the request leaves evidence instead of evaporating.
        """
        if not required_capabilities:
            raise DiscussionParticipantError(
                "a discussion must name the capabilities it needs; participant selection is "
                "explicit, never implied by the whole roster"
            )

        goal = await self.planning_store.get_goal(goal_id)
        if goal is None:
            raise DiscussionStateError(f"unknown goal {goal_id}")
        if str(goal["project_id"]) != str(project_id):
            raise DiscussionStateError(
                f"goal {goal_id} belongs to project {goal['project_id']}, not {project_id}"
            )

        # The revision the team is deliberating against. Resolved from lineage rather than taken
        # on trust, so the discussion is bound to what is actually current at the moment it opens.
        revision = None
        if plan_revision_id is not None:
            revision = await self.planning_store.get_revision(plan_revision_id)
            if revision is None or str(revision["goal_id"]) != str(goal_id):
                raise DiscussionStateError(
                    f"plan revision {plan_revision_id} is not a revision of goal {goal_id}"
                )
            # A revision that is already superseded is stale before the discussion says a word, and
            # nothing the team concluded about it could ever be consumed by M3.4 -- whose currency
            # precondition this discussion would fail from the moment it opened. Refuse here, where
            # it costs nothing, rather than spend a reasoning budget arriving at the same place.
            #
            # This is a caller error, not a race, and it is NOT the safety boundary: mid-flight
            # supersession is legitimate and is deliberately not policed (see the class docstring
            # and AT-M3.3-PLAN-STALENESS-DESIGN-REVIEW-1). The boundary that actually protects the
            # plan is M3.2's compare-and-swap at the moment a successor is written.
            if not await self.planning_store.is_current(plan_revision_id):
                raise DiscussionStateError(
                    f"plan revision {plan_revision_id} has already been superseded; a discussion "
                    "may not open against a revision that is not current"
                )
        else:
            revision = await self.planning_store.get_current_revision(goal_id)

        limits = bounds or DiscussionBounds()
        key = idempotency_key or derive_idempotency_key(
            project_id=project_id,
            goal_id=goal_id,
            plan_revision_id=revision["plan_revision_id"] if revision else None,
            topic=topic,
        )

        existing = await self.store.get_session_by_key(key)
        if existing is not None:
            return existing

        payload = {
            "project_id": project_id,
            "goal_id": goal_id,
            "plan_revision_id": revision["plan_revision_id"] if revision else None,
            "opened_by": opened_by,
            "topic": topic,
            "required_capabilities": list(required_capabilities),
            "idempotency_key": key,
            **limits.model_dump(),
        }

        participants, uncovered = await self.select_participants(project_id, required_capabilities)
        if uncovered or len(participants) < MIN_PARTICIPANTS:
            # Two different failures, and the record says which. An uncovered capability means the
            # team lacks a skill the topic needs; a covered-but-too-small roster means one agent
            # answers for everything, which is a monologue rather than a deliberation. The first
            # is fixed by adding a capability, the second by adding an agent, so reporting either
            # under the other's name points the reader at the wrong repair.
            stop_reason = (
                "insufficient_capability_coverage" if uncovered else "insufficient_participants"
            )
            session = await self.store.create_failed_session(payload, stop_reason=stop_reason)
            await self._audit(
                discussion_events.AUDIT_DISCUSSION_CLOSED,
                f"discussion {session['discussion_id']} could not open for goal {goal_id}",
                stop_reason,
                {
                    "discussion_id": str(session["discussion_id"]),
                    "goal_id": str(goal_id),
                    "uncovered_capabilities": [u["capability"] for u in uncovered],
                    "participants_selected": str(len(participants)),
                    "minimum_participants": str(MIN_PARTICIPANTS),
                },
            )
            return session

        created, session = await self.store.create_session(payload, participants)
        if created:
            await self._audit(
                discussion_events.AUDIT_DISCUSSION_OPENED,
                f"discussion {session['discussion_id']} opened for goal {goal_id}",
                "open",
                {
                    "discussion_id": str(session["discussion_id"]),
                    "project_id": str(project_id),
                    "goal_id": str(goal_id),
                    "plan_revision_id": (
                        str(session["plan_revision_id"]) if session["plan_revision_id"] else None
                    ),
                    "thread_id": str(session["thread_id"]),
                    "participants": str(len(participants)),
                    "max_rounds": str(session["max_rounds"]),
                },
            )
        return session

    async def cancel(self, discussion_id: str) -> dict[str, Any] | None:
        """Abort an open discussion. Already-terminal discussions are left exactly as they are."""
        session = await self.store.close_session(discussion_id, stop_reason="cancelled")
        if session is not None:
            await self._audit(
                discussion_events.AUDIT_DISCUSSION_CLOSED,
                f"discussion {discussion_id} cancelled",
                "cancelled",
                {"discussion_id": str(discussion_id), "stop_reason": "cancelled"},
            )
        return session

    # --- advancing -----------------------------------------------------------------------------

    async def advance(self, discussion_id: str) -> dict[str, Any]:
        """Take at most ONE step: one turn, one round boundary, or one closure.

        One step per call on purpose. It makes the concurrency question answerable -- several
        workers calling this at once contend for exactly one slot, and the database says who won --
        and it makes a resumed process's next action a pure function of the durable rows.

        Returns ``{"advanced": bool, "session": ..., "turn": ..., "detail": str}``. ``advanced`` is
        False both when the discussion is already terminal and when this worker lost the race;
        those are different ``detail`` values, never different exceptions, because losing a race is
        an expected outcome rather than a fault.
        """
        session = await self.store.get_session(discussion_id)
        if session is None:
            raise DiscussionStateError(f"unknown discussion {discussion_id}")

        # PRECEDENCE, in the order STOP_REASON_PRECEDENCE fixes.
        # 1. An already-terminal discussion is left exactly as it is.
        if session["state"] != "open":
            return self._result(False, session, None, f"discussion is {session['state']}")

        # 2. The wall clock, before anything else is attempted. Checkpoint A of four: no slot is
        #    claimed and no provider is called after the deadline has passed. This is also the
        #    check that makes a discussion whose worker died mid-turn terminal at all -- counters
        #    cannot advance without a worker, so no count bound could ever fire for it.
        if session["deadline_expired"]:
            return await self._expire(session)

        participants = await self.store.list_participants(discussion_id)
        count = len(participants)
        if count < MIN_PARTICIPANTS:
            # The capabilities were covered when this opened, or it would never have opened. What
            # is wrong NOW is the count, and saying "insufficient capability coverage" would send
            # a reader to look at the roster's skills rather than at its size.
            won, current = await self._close(discussion_id, stop_reason="insufficient_participants")
            return self._result(
                won, current or session, None, f"{count} participant(s) is not a discussion"
            )

        round_index = session["current_round"]
        round_turns = await self.store.list_turns(discussion_id, round_index)
        recorded_seats = {t["seat_index"] for t in round_turns if t["status"] == "recorded"}

        # The round's participant seats are done; decide what happens at the boundary.
        if recorded_seats >= set(range(count)):
            return await self._close_round(session, participants, round_turns)

        # Budgets are checked BEFORE a slot is claimed, so an exhausted discussion never starts a
        # turn it is not allowed to finish.
        exceeded = self._budget_exceeded(session)
        if exceeded:
            won, current = await self._close(discussion_id, stop_reason=exceeded)
            return self._result(won, current or session, None, exceeded)

        seat = min(set(range(count)) - recorded_seats)
        participant = participants[seat]
        if participant["turns_taken"] >= session["max_turns_per_participant"]:
            # Its OWN bound, not the round bound. The discussion may have rounds left; this
            # participant does not, and that is the fact worth recording.
            won, current = await self._close(
                discussion_id, stop_reason="participant_turn_limit_reached"
            )
            return self._result(
                won,
                current or session,
                None,
                f"{participant['agent_key']} used all "
                f"{session['max_turns_per_participant']} of its turns",
            )

        available = await self._participant_available(session["project_id"], participant)
        if not available:
            won, current = await self._close(discussion_id, stop_reason="participant_unavailable")
            return self._result(
                won, current or session, None, f"{participant['agent_key']} is no longer available"
            )

        turn_plan = plan_turn(round_index, seat, count)
        addressee = (
            participants[turn_plan.addresses_seat] if turn_plan.addresses_seat is not None else None
        )
        return await self._take_turn(
            session=session,
            participants=participants,
            participant=participant,
            addressee=addressee,
            round_index=round_index,
            seat_index=seat,
            reasoning_verb=turn_plan.reasoning_verb,
            addressed_team=turn_plan.addresses_team,
        )

    async def run(self, discussion_id: str, max_steps: int | None = None) -> dict[str, Any]:
        """Advance repeatedly until the discussion is terminal or stops making progress.

        Bounded twice over: by the discussion's own persisted limits, which is what actually ends
        it, and by ``max_steps``, which only guards against a caller looping on a discussion that
        stopped progressing for an external reason.
        """
        session = await self.store.get_session(discussion_id)
        if session is None:
            raise DiscussionStateError(f"unknown discussion {discussion_id}")
        ceiling = max_steps or (
            session["max_rounds"] * (session["max_messages"] + 4) + session["max_rounds"] + 8
        )
        for _ in range(ceiling):
            outcome = await self.advance(discussion_id)
            session = outcome["session"]
            if session["state"] != "open" or not outcome["advanced"]:
                return outcome
        return self._result(False, session, None, "step ceiling reached without a terminal state")

    # --- internals -----------------------------------------------------------------------------

    @staticmethod
    def _result(
        advanced: bool, session: dict[str, Any], turn: dict[str, Any] | None, detail: str
    ) -> dict[str, Any]:
        return {"advanced": advanced, "session": session, "turn": turn, "detail": detail}

    @staticmethod
    def _budget_exceeded(session: dict[str, Any]) -> str | None:
        """The count bound that prevents the next unit of work, in fixed precedence order."""
        if session["messages_posted"] >= session["max_messages"]:
            return "message_limit_reached"
        if session["invocations_started"] >= session["max_invocations"]:
            return "invocation_limit_reached"
        return None

    async def _expire(self, session: dict[str, Any]) -> dict[str, Any]:
        """Close a discussion whose deadline has passed. Idempotent, and safe to race.

        The DB re-checks the deadline on the write, so a worker with a fast clock cannot expire a
        discussion early, and of many workers observing the same expiry exactly one performs the
        transition while the rest report the same terminal state.
        """
        won, current = await self._close(
            str(session["discussion_id"]), stop_reason="timeout_reached"
        )
        return self._result(
            won, current or session, None, "the discussion's elapsed-time deadline passed"
        )

    async def _participant_available(self, project_id: Any, participant: dict[str, Any]) -> bool:
        """Is this participant still an active member with an active profile?

        Re-read every turn rather than trusted from selection time: a member can be paused or an
        agent disabled while a discussion is in flight, and continuing to put words in its mouth
        would be worse than stopping.
        """
        candidates = await self.team_store.routing_candidates(str(project_id))
        for candidate in candidates:
            if candidate.principal_id == str(participant["principal_id"]):
                return (
                    candidate.membership_state == "active" and candidate.profile_status == "active"
                )
        return False

    async def _close_round(
        self,
        session: dict[str, Any],
        participants: list[dict[str, Any]],
        round_turns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """The round's participants have all spoken. Converge, exhaust, or move to the next round."""
        discussion_id = str(session["discussion_id"])
        round_index = session["current_round"]
        participant_turns = [t for t in round_turns if t["seat_index"] < len(participants)]
        verdict = evaluate_convergence(participant_turns)

        # Checkpoint D. A round boundary is reached after N provider calls, so this is the second
        # place elapsed time realistically runs out. Converging here would write a summary message
        # and a result reference after the discussion's own bound expired -- an outcome produced
        # outside the window the team was given, presented as if it had been produced inside it.
        latest = await self.store.get_session(discussion_id) or session
        if latest["state"] != "open":
            return self._result(False, latest, None, f"discussion is {latest['state']}")
        if latest["deadline_expired"]:
            return await self._expire(latest)

        if verdict.converged:
            return await self._converge(session, participants, round_index)

        if round_index >= session["max_rounds"]:
            won, current = await self._close(discussion_id, stop_reason="round_limit_reached")
            return self._result(won, current or session, None, verdict.reason)

        moved = await self.store.advance_round(discussion_id, round_index)
        return self._result(
            moved is not None,
            moved or await self.store.get_session(discussion_id),
            None,
            f"round {round_index} closed unresolved: {verdict.reason}",
        )

    async def _converge(
        self, session: dict[str, Any], participants: list[dict[str, Any]], round_index: int
    ) -> dict[str, Any]:
        """Record the discussion's own summary, then close as converged.

        The summary is a TeamMessage and a durable reference on the session -- the structured
        input M3.4 will consume. It is emphatically NOT a TeamDecision: nothing selects an option
        on the team's behalf here, and ``resulting_plan_revision_id`` stays untouched.
        """
        discussion_id = str(session["discussion_id"])
        seat = summary_seat(len(participants))
        speaker = participants[0]

        outcome = await self._take_turn(
            session=session,
            participants=participants,
            participant=speaker,
            addressee=None,
            round_index=round_index,
            seat_index=seat,
            reasoning_verb="summarize_decision",
            addressed_team=True,
        )
        turn = outcome["turn"]
        if turn is None or turn.get("status") != "recorded":
            return outcome

        won, current = await self._close(
            discussion_id,
            stop_reason="convergence_reached",
            result_message_id=turn["message_id"],
        )
        return self._result(won, current or session, turn, "convergence reached")

    async def _close(
        self,
        discussion_id: str,
        *,
        stop_reason: str,
        result_message_id: Any = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Close the discussion and report whether THIS caller was the one that closed it.

        ``close_session`` is conditional on the discussion still being open, so of several workers
        reaching the same terminal condition together exactly one gets a row back. Returning that
        fact rather than discarding it is what keeps ``advanced`` truthful: a worker that lost the
        closure race changed nothing, and saying otherwise would make the flag useless for
        deciding whether anything actually happened. The session returned is always the current
        one, so the loser still reports the real terminal state.

        Deadline precedence is enforced HERE, in the write, rather than by the order of the checks
        in :meth:`advance`. Every reason but the two in ``_UNGUARDED_CLOSE_REASONS`` is written
        under ``now() < deadline_at``, so a verdict this worker reached before the wall clock ran
        out but is writing after it cannot land. When that guard refuses, the deadline is the fact
        that is actually true and the discussion closes as a timeout -- which is what makes the
        precedence in ``STOP_REASON_PRECEDENCE`` a property of the database rather than a property
        of whichever worker happened to get there first.
        """
        guarded = stop_reason not in _UNGUARDED_CLOSE_REASONS
        closed = await self.store.close_session(
            discussion_id,
            stop_reason=stop_reason,
            result_message_id=result_message_id,
            require_open_deadline=guarded,
        )
        if closed is not None:
            await self._audit_close(closed, stop_reason)
            return True, closed

        current = await self.store.get_session(discussion_id)
        if (
            guarded
            and current is not None
            and current["state"] == "open"
            and current["deadline_expired"]
        ):
            return await self._close(discussion_id, stop_reason="timeout_reached")
        return False, current or {}

    async def _audit_close(self, session: dict[str, Any], stop_reason: str) -> None:
        await self._audit(
            discussion_events.AUDIT_DISCUSSION_CLOSED,
            f"discussion {session['discussion_id']} closed",
            stop_reason,
            {
                "discussion_id": str(session["discussion_id"]),
                "goal_id": str(session["goal_id"]),
                "state": session["state"],
                "stop_reason": stop_reason,
                "rounds_used": str(session["current_round"]),
                "turns_taken": str(session["turns_taken"]),
                "result_message_id": (
                    str(session["result_message_id"]) if session.get("result_message_id") else None
                ),
            },
        )

    async def _take_turn(
        self,
        *,
        session: dict[str, Any],
        participants: list[dict[str, Any]],
        participant: dict[str, Any],
        addressee: dict[str, Any] | None,
        round_index: int,
        seat_index: int,
        reasoning_verb: str,
        addressed_team: bool,
    ) -> dict[str, Any]:
        """Claim one slot, reason once, post one message. Every failure path is deterministic."""
        discussion_id = str(session["discussion_id"])
        correlation_id = derive_correlation_id(discussion_id, round_index, seat_index)

        owned, turn = await self.store.claim_turn(
            {
                "discussion_id": discussion_id,
                "round_index": round_index,
                "seat_index": seat_index,
                "speaker_principal_id": participant["principal_id"],
                "addressed_principal_id": addressee["principal_id"] if addressee else None,
                "addressed_team": addressed_team,
                "intent": _PROVISIONAL_INTENT[reasoning_verb],
                "reasoning_verb": reasoning_verb,
                "correlation_id": correlation_id,
            }
        )

        if not owned:
            resolved = await self._resolve_unowned_turn(session, turn, correlation_id)
            if resolved is not None:
                return resolved
            # Falling through means the slot's previous claimant never reached the provider, so
            # taking it over consumes nothing. Two workers taking it over together is still safe:
            # AT-M3.1's correlation-id claim admits exactly one of them, and only that one can
            # produce a message.

        if turn is None:
            return self._result(False, session, None, "turn slot vanished between claim and read")
        return await self._reason_and_record(
            session=session,
            participants=participants,
            participant=participant,
            addressee=addressee,
            turn=turn,
            round_index=round_index,
            seat_index=seat_index,
            reasoning_verb=reasoning_verb,
            correlation_id=correlation_id,
        )

    async def _resolve_unowned_turn(
        self, session: dict[str, Any], turn: dict[str, Any] | None, correlation_id: str
    ) -> dict[str, Any] | None:
        """What to do about a slot someone else already holds. ``None`` means "safe to take over".

        Three genuinely different situations, and conflating them is how a duplicate reply or a
        stuck discussion happens:

        * already ``recorded`` -- this is a duplicate or a retry of a finished turn. A no-op.
        * ``claimed`` with no reasoning invocation -- the previous claimant died before calling the
          provider, so nothing was consumed and this worker may take over. Both takers would still
          resolve to one provider call, because AT-M3.1 owns the derived correlation id.
        * ``claimed`` with a TERMINAL invocation -- the provider already ran for this turn and its
          artifact is gone; AT-M3.1 persists metadata, never content, so there is nothing to
          reconstruct and re-invoking would be a second call for one turn. Fail closed.
        """
        discussion_id = str(session["discussion_id"])
        if turn is None:
            return self._result(False, session, None, "turn slot vanished between claim and read")
        if turn["status"] == "recorded":
            return self._result(False, session, turn, "turn already recorded")
        if turn["status"] == "failed":
            return self._result(False, session, turn, "turn already failed")

        status = await self.store.invocation_status(correlation_id)
        if status is None:
            return None
        if status == "started":
            # Checkpoint B. "Another worker is resolving this turn" is true right up until that
            # worker dies, and a STARTED invocation whose owner is gone never becomes anything
            # else: AT-M3.1 will not re-issue it under the same correlation id, and no counter on
            # this discussion can move without it. Before this check the discussion stayed open
            # forever -- the exact Validation-1 failure. The deadline is re-read rather than taken
            # from the session this call started with, because the wait for the other worker is
            # itself elapsed time and may have crossed the boundary.
            latest = await self.store.get_session(discussion_id) or session
            if latest["state"] != "open":
                return self._result(False, latest, turn, f"discussion is {latest['state']}")
            if latest["deadline_expired"]:
                return await self._expire(latest)
            return self._result(False, session, turn, "another worker is resolving this turn")

        await self.store.fail_turn(turn["turn_id"])
        won, current = await self._close(discussion_id, stop_reason="reasoning_provider_failure")
        return self._result(
            won,
            current or session,
            turn,
            f"turn is unresolvable: its reasoning invocation is {status} but no message was written",
        )

    async def _reason_and_record(
        self,
        *,
        session: dict[str, Any],
        participants: list[dict[str, Any]],
        participant: dict[str, Any],
        addressee: dict[str, Any] | None,
        turn: dict[str, Any],
        round_index: int,
        seat_index: int,
        reasoning_verb: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        discussion_id = str(session["discussion_id"])
        context = await self._context_for(
            session=session, participant=participant, round_index=round_index, verb=reasoning_verb
        )

        request = ReasoningRequest(
            verb=reasoning_verb,  # type: ignore[arg-type]
            context=context,
            project_id=str(session["project_id"]),
            thread_id=str(session["thread_id"]),
            requested_by_principal_id=str(participant["principal_id"]),
            round_number=round_index,
            correlation_id=correlation_id,
        )
        result = await self.reasoning.invoke(request, provider=self.provider)

        if result.artifact is None:
            # Only a FRESH call with no artifact is this worker's provider failure. Any other
            # disposition means AT-M3.1 resolved this correlation id to someone else's attempt --
            # 'in_progress' while they are still working, 'replay' once they finished -- and
            # neither is a fault of the discussion. Treating a replay as a failure here would let
            # a losing racer close a discussion whose turn actually succeeded. If that other
            # attempt genuinely died without writing its message, the NEXT advance sees a claimed
            # turn against a terminal invocation and fails the discussion closed there.
            if result.disposition != "fresh":
                return self._result(
                    False,
                    session,
                    turn,
                    f"another worker owns this reasoning call ({result.disposition})",
                )
            await self.store.fail_turn(
                turn["turn_id"], reasoning_invocation_id=result.invocation.get("invocation_id")
            )
            won, current = await self._close(
                discussion_id, stop_reason="reasoning_provider_failure"
            )
            detail = (
                f"reasoning {result.invocation.get('status')}"
                f"/{result.invocation.get('failure_category')}"
            )
            return self._result(won, current or session, turn, detail)

        # Checkpoint C, and the one that decides whether the timeout bound means anything. The
        # provider call is the only step here that can take real time, so the deadline can pass
        # while it runs -- and by the time it returns another worker may already have closed this
        # discussion. Re-read before writing ANYTHING: a TeamMessage posted after the discussion
        # ended would be a participant speaking after the room closed, and a thread that can gain
        # messages after its terminal state is not evidence of what the team said.
        #
        # The invocation itself is left exactly as AT-M3.1 recorded it. It truthfully says a
        # provider was called and what came back; deleting it to tidy up would destroy the only
        # record of a call that really happened. What is refused is the discussion CONSUMING it.
        latest = await self.store.get_session(discussion_id) or session
        if latest["state"] != "open" or latest["deadline_expired"]:
            await self.store.fail_turn(
                turn["turn_id"], reasoning_invocation_id=result.invocation.get("invocation_id")
            )
            if latest["state"] != "open":
                return self._result(
                    False,
                    latest,
                    turn,
                    f"reasoning returned after the discussion closed ({latest['stop_reason']}); "
                    "its result was not posted",
                )
            outcome = await self._expire(latest)
            outcome["detail"] = (
                "reasoning returned after the deadline passed; its result was not posted"
            )
            return outcome

        intent, concern_count = classify_intent(
            reasoning_verb=reasoning_verb,
            artifact=result.artifact,
            seat_index=seat_index,
            round_index=round_index,
        )
        message = await self.team_store.post_message(
            {
                "thread_id": str(session["thread_id"]),
                "project_id": str(session["project_id"]),
                "sender_principal_id": str(participant["principal_id"]),
                "recipient_principal_id": (str(addressee["principal_id"]) if addressee else None),
                "recipient_team": addressee is None,
                "message_type": MESSAGE_TYPE_FOR_INTENT[intent],
                "summary": result.artifact.summary[:2000],
                "content": result.artifact.as_safe_dict(),
                "artifact_refs": {
                    "discussion_id": discussion_id,
                    "goal_id": str(session["goal_id"]),
                    "plan_revision_id": (
                        str(session["plan_revision_id"]) if session["plan_revision_id"] else None
                    ),
                    "reasoning_invocation_id": str(result.invocation["invocation_id"]),
                    "round": round_index,
                    "intent": intent,
                },
            }
        )

        recorded = await self.store.complete_turn(
            turn["turn_id"],
            intent=intent,
            concern_count=concern_count,
            message_id=message["message_id"],
            reasoning_invocation_id=result.invocation["invocation_id"],
            discussion_id=discussion_id,
            seat_index=seat_index,
        )
        if recorded is None:
            return self._result(False, session, turn, "another worker recorded this turn first")

        await self._audit(
            discussion_events.AUDIT_DISCUSSION_TURN_RECORDED,
            f"round {round_index} seat {seat_index} of discussion {discussion_id} recorded",
            intent,
            {
                "discussion_id": discussion_id,
                "goal_id": str(session["goal_id"]),
                "thread_id": str(session["thread_id"]),
                "speaker_principal_id": str(participant["principal_id"]),
                "round": str(round_index),
                "seat": str(seat_index),
                "intent": intent,
                "message_id": str(message["message_id"]),
                "reasoning_invocation_id": str(result.invocation["invocation_id"]),
                "concern_count": str(concern_count),
            },
        )
        return self._result(
            True, await self.store.get_session(discussion_id) or session, recorded, intent
        )

    async def _context_for(
        self, *, session: dict[str, Any], participant: dict[str, Any], round_index: int, verb: str
    ) -> dict[str, Any]:
        """Bounded reasoning input, assembled from approved durable artifacts only."""
        goal = await self.planning_store.get_goal(session["goal_id"]) or {}
        revision = (
            await self.planning_store.get_revision(session["plan_revision_id"])
            if session["plan_revision_id"]
            else None
        )
        messages = await self.team_store.list_messages(
            str(session["project_id"]), str(session["thread_id"])
        )
        standing = next(
            (m["summary"] for m in reversed(messages) if m["message_type"] == "proposal"), None
        )
        context = build_turn_context(
            topic=session["topic"],
            round_index=round_index,
            goal=goal,
            plan_revision=revision,
            recent_messages=messages,
            speaker=participant,
            standing_proposal_summary=standing,
        )
        if verb == "summarize_decision":
            # The options the team actually put on the table, as they were summarised in the
            # thread. Naming them is not choosing between them.
            context["options_considered"] = [
                m["summary"][:200] for m in messages if m["message_type"] == "proposal"
            ] or ["proceed with the standing proposal"]
        return context

    # --- reads ---------------------------------------------------------------------------------

    async def get_discussion(self, discussion_id: str) -> dict[str, Any] | None:
        return await self.store.get_session(discussion_id)

    async def plan_currency(self, session: dict[str, Any]) -> dict[str, Any]:
        """Whether the revision this discussion is bound to is still the Goal's current one.

        DERIVED on every read and stored nowhere. AT-M3.2 keeps currency as a property of lineage
        -- the tip is the revision nothing supersedes -- with no status column and no UPDATE on a
        predecessor, and a cached copy here would be this project's first denormalised answer to a
        question the lineage already answers exactly. It would also need a writer, a race story and
        a repair path, none of which exist while the fact stays computed.

        The binding itself never moves: ``plan_revision_id`` is immutable by trigger, and a
        discussion is permanently about the exact revision it opened against. What this reports is
        the world moving around it.

        A discussion bound to NO revision -- legitimate, since deciding what the first plan should
        be is itself a discussion -- is current exactly while the Goal still has no plan. That is
        the same statement as the bound case, not a special case: the premise the team deliberated
        under either still holds or it does not.
        """
        current = await self.planning_store.get_current_revision(session["goal_id"])
        current_id = current["plan_revision_id"] if current else None
        bound = session.get("plan_revision_id")
        if bound is None:
            is_current = current_id is None
        else:
            is_current = await self.planning_store.is_current(bound)
        return {
            "plan_revision_is_current": is_current,
            "current_plan_revision_id": str(current_id) if current_id else None,
        }

    async def get_participants(self, discussion_id: str) -> list[dict[str, Any]]:
        return await self.store.list_participants(discussion_id)

    async def get_turns(self, discussion_id: str) -> list[dict[str, Any]]:
        return await self.store.list_turns(discussion_id)

    async def get_messages(self, discussion_id: str, limit: int = 200) -> list[dict[str, Any]]:
        session = await self.store.get_session(discussion_id)
        if session is None:
            return []
        return await self.team_store.list_messages(
            str(session["project_id"]), str(session["thread_id"]), limit=limit
        )


__all__ = ["DiscussionService"]
