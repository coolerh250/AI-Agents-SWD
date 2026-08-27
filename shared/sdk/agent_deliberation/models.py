"""Step AT-M3.3 -- bounded team discussion: states, turn planning, and the convergence signal.

Pure. Nothing here performs I/O, so the turn a discussion takes next is a function of the durable
rows that were read, and the same rows always produce the same next turn. That is what makes the
runtime resumable: a new process reads the ledger and recomputes, rather than remembering.

This module is named ``agent_deliberation`` and not ``agent_discussion`` deliberately.
``shared/sdk/agent_discussion/`` already exists and is the Stage 46 deterministic-template review
FIXTURE that collaboration-and-workroom-model.md section 1 supersedes as the collaboration model
and section 9 forbids describing as multi-agent participation. Reusing its name would blur exactly
the line that document draws.

Three boundaries this module is built to keep:

* **A proposal here is a discussion artifact, nothing more.** It is not an M3.4 Proposal domain
  object, not a TeamDecision, not a human Approval and not an accepted PlanRevision. Nothing in
  this slice writes any of those.
* **Consensus is never inferred from exhaustion.** Convergence is a function of what participants
  actually said -- specifically, of whether the standing proposal still has unresolved concerns --
  and never of how many rounds have elapsed. The database enforces the same separation.
* **No hidden reasoning.** The reasoning context assembled here is passed to AT-M3.1 in memory and
  is never persisted by anything in this slice.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from shared.sdk.agent_reasoning.models import (
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ProposalArtifact,
)

# --- vocabulary ---------------------------------------------------------------------------------

DiscussionState = Literal["open", "converged", "exhausted", "failed", "cancelled"]
DISCUSSION_STATES: tuple[str, ...] = ("open", "converged", "exhausted", "failed", "cancelled")

StopReason = Literal[
    "convergence_reached",
    "round_limit_reached",
    "message_limit_reached",
    "invocation_limit_reached",
    "participant_unavailable",
    "reasoning_provider_failure",
    "cancelled",
    "insufficient_capability_coverage",
]

#: The state each stop reason implies. Mirrors migration 039's
#: ``chk_discussion_sessions_reason_matches_state``: "the team agreed" and "the team ran out of
#: rounds" are different outcomes, and no code path may record one as the other.
STATE_FOR_STOP_REASON: dict[str, DiscussionState] = {
    "convergence_reached": "converged",
    "round_limit_reached": "exhausted",
    "message_limit_reached": "exhausted",
    "invocation_limit_reached": "exhausted",
    "participant_unavailable": "failed",
    "reasoning_provider_failure": "failed",
    "insufficient_capability_coverage": "failed",
    "cancelled": "cancelled",
}

TurnIntent = Literal[
    "proposal",
    "challenge",
    "response",
    "observation",
    "clarification",
    "support",
    "objection",
    "convergence_summary",
]

#: Which AT-M2 ``team_messages.message_type`` carries each discussion intent.
#:
#: The AT-M2 vocabulary is not widened to hold the discussion's intents, because AT-D14 pre-cleared
#: exactly one alteration of an AT-M2 table and this is not it. The intent stays on the turn ledger
#: and the message is posted under the type the collaboration contract already defines for it.
#:
#: ``convergence_summary`` maps to ``message``, NOT to ``decision_summary``: the contract's own
#: table says ``decision_summary`` "points at a TeamDecision" and CHANGES STATE. M3.3 records no
#: TeamDecision, so posting one would announce a decision that does not exist.
MESSAGE_TYPE_FOR_INTENT: dict[str, str] = {
    "proposal": "proposal",
    "challenge": "challenge",
    "objection": "challenge",
    "response": "message",
    "observation": "message",
    "clarification": "message",
    "support": "message",
    "convergence_summary": "message",
}

#: Intents that mean the speaker still has something unresolved with the standing proposal. The
#: convergence signal is the absence of these in a completed round.
UNRESOLVED_INTENTS: frozenset[str] = frozenset({"challenge", "objection", "clarification"})

TurnStatus = Literal["claimed", "recorded", "failed"]

#: The convergence-summary turn is spoken by seat 0 but belongs to no participant's turn budget,
#: so it sits at the seat index one past the last participant.
SUMMARY_SEAT_OFFSET = 0

#: A deliberation needs someone to answer back. One participant is a monologue, and calling it a
#: team discussion would be the same false-complete risk INV-07 exists to catch.
MIN_PARTICIPANTS = 2

_CORRELATION_NAMESPACE = uuid.UUID("6f0d5b1a-9a3e-4a6d-9c2f-3f7f1a6b8d40")


# --- errors -------------------------------------------------------------------------------------


class DiscussionBoundsError(ValueError):
    """A bound was absent, out of range, or changed after the discussion opened."""


class DiscussionParticipantError(ValueError):
    """A participant could not be selected, or was selected twice."""


class DiscussionStateError(ValueError):
    """An operation that is not legal in the discussion's current state."""


class DiscussionTurnLost(RuntimeError):
    """This worker did not win the slot it tried to claim.

    Not an error condition in the normal sense: it is the expected outcome for every worker but
    one when several advance the same discussion concurrently, and the caller's correct response
    is to re-read the discussion, not to retry the claim.
    """

    def __init__(self, *, discussion_id: str, round_index: int, seat_index: int) -> None:
        self.discussion_id = discussion_id
        self.round_index = round_index
        self.seat_index = seat_index
        super().__init__(
            f"turn (round {round_index}, seat {seat_index}) of discussion {discussion_id} was "
            "claimed by another worker"
        )


class DiscussionTurnUnresolvable(RuntimeError):
    """A claimed turn cannot be completed and cannot be safely retried.

    Reached when a previous attempt's reasoning invocation already reached a terminal outcome but
    its message was never written. AT-M3.1 persists call METADATA and never artifact content, so
    there is nothing to reconstruct, and re-invoking under a fresh correlation_id would be a
    second provider call for one logical turn. The discussion fails closed instead.
    """


# --- bounds -------------------------------------------------------------------------------------


class DiscussionBounds(BaseModel):
    """What stops the discussion. Persisted on the session row, never re-derived at runtime.

    A resumed process must enforce the limits the OPENING process was given, so these are read
    back from the database rather than recomputed from defaults that may since have changed.
    """

    model_config = ConfigDict(extra="forbid")

    max_rounds: int = Field(default=3, ge=1, le=20)
    max_messages: int = Field(default=24, ge=1, le=200)
    max_invocations: int = Field(default=24, ge=1, le=200)
    max_turns_per_participant: int = Field(default=3, ge=1, le=20)


# --- durable shapes -----------------------------------------------------------------------------


class DiscussionParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: uuid.UUID | None = None
    discussion_id: uuid.UUID | None = None
    principal_id: uuid.UUID
    agent_key: str = Field(min_length=1, max_length=200)
    functional_role: str = Field(min_length=1, max_length=200)
    matched_capabilities: tuple[str, ...] = ()
    selection_reason: str = Field(min_length=1, max_length=1000)
    seat_index: int = Field(ge=0)
    turns_taken: int = Field(default=0, ge=0)


class DiscussionTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: uuid.UUID
    discussion_id: uuid.UUID
    round_index: int = Field(ge=1)
    seat_index: int = Field(ge=0)
    speaker_principal_id: uuid.UUID
    addressed_principal_id: uuid.UUID | None = None
    addressed_team: bool = False
    intent: TurnIntent
    reasoning_verb: str
    reasoning_invocation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    correlation_id: uuid.UUID
    status: TurnStatus
    concern_count: int = Field(default=0, ge=0)


class DiscussionSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discussion_id: uuid.UUID
    project_id: uuid.UUID
    goal_id: uuid.UUID
    plan_revision_id: uuid.UUID | None = None
    thread_id: uuid.UUID
    opened_by: uuid.UUID
    topic: str = Field(min_length=1, max_length=2000)
    required_capabilities: tuple[str, ...] = ()
    max_rounds: int = Field(ge=1)
    max_messages: int = Field(ge=1)
    max_invocations: int = Field(ge=1)
    max_turns_per_participant: int = Field(ge=1)
    current_round: int = Field(ge=1)
    turns_taken: int = Field(ge=0)
    messages_posted: int = Field(ge=0)
    invocations_started: int = Field(ge=0)
    state: DiscussionState
    stop_reason: StopReason | None = None
    result_message_id: uuid.UUID | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state != "open"


# --- deterministic identity ---------------------------------------------------------------------


def derive_correlation_id(discussion_id: Any, round_index: int, seat_index: int) -> str:
    """The reasoning correlation id for one turn slot.

    Derived, not random, so a retry of the SAME slot is recognised by AT-M3.1 as the same logical
    attempt. That is the second of the two independent guarantees against a duplicate provider
    call: the slot claim is the first.
    """
    return str(uuid.uuid5(_CORRELATION_NAMESPACE, f"{discussion_id}:{round_index}:{seat_index}"))


def derive_idempotency_key(
    *, project_id: Any, goal_id: Any, plan_revision_id: Any, topic: str
) -> str:
    """The default duplicate-start key.

    A caller that re-issues the same start request -- same project, same Goal, same revision, same
    question -- gets the discussion it already started rather than a second one talking past it. A
    caller that genuinely wants a second deliberation on the same topic passes its own key.
    """
    raw = f"{project_id}|{goal_id}|{plan_revision_id or ''}|{topic.strip()}"
    return "auto:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


# --- turn planning ------------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnPlan:
    """What the runtime asks of one slot. The INTENT is not decided here.

    The plan fixes who speaks, to whom, and which reasoning verb is used. What the turn turns out
    to MEAN -- challenge, support, clarification -- is read from the artifact afterwards by
    :func:`classify_intent`, because a script that decided in advance that seat 2 objects would
    make the convergence signal a formality.
    """

    round_index: int
    seat_index: int
    reasoning_verb: str
    addresses_seat: int | None
    addresses_team: bool


def plan_turn(round_index: int, seat_index: int, participant_count: int) -> TurnPlan:
    """The deterministic shape of one turn.

    Seat 0 opens each round -- proposing in round 1, responding to the round's critiques
    afterwards -- and broadcasts to the team. Every other seat addresses seat 0, because a
    critique nobody is asked to answer is not part of a deliberation.
    """
    if participant_count < MIN_PARTICIPANTS:
        raise DiscussionParticipantError(
            f"a discussion needs at least {MIN_PARTICIPANTS} participants; got {participant_count}"
        )
    if seat_index == 0:
        verb = "propose" if round_index == 1 else "critique"
        return TurnPlan(
            round_index=round_index,
            seat_index=0,
            reasoning_verb=verb,
            addresses_seat=None,
            addresses_team=True,
        )
    return TurnPlan(
        round_index=round_index,
        seat_index=seat_index,
        reasoning_verb="critique",
        addresses_seat=0,
        addresses_team=False,
    )


def summary_seat(participant_count: int) -> int:
    """The seat index of the convergence-summary turn: one past the last participant."""
    return participant_count + SUMMARY_SEAT_OFFSET


def classify_intent(
    *,
    reasoning_verb: str,
    artifact: ProposalArtifact | CritiqueArtifact | DecisionSummaryArtifact,
    seat_index: int,
    round_index: int,
) -> tuple[TurnIntent, int]:
    """What the turn meant, and how many unresolved concerns it carried.

    Read from the artifact, never from the seat's script:

    * ``propose`` is always a proposal.
    * ``summarize_decision`` is always the convergence summary.
    * a critique with concerns is a challenge -- an objection when it comes from seat 0, whose
      round-2+ turn is a response to the team rather than a critique of a peer;
    * a critique with questions but no concerns is a clarification -- unresolved, but a request
      rather than a disagreement;
    * a critique with neither is support, or a plain response from seat 0.

    The count is what the convergence signal sums; the label is what a human reads.
    """
    if reasoning_verb == "propose":
        return "proposal", 0
    if reasoning_verb == "summarize_decision":
        return "convergence_summary", 0

    if not isinstance(artifact, CritiqueArtifact):
        raise DiscussionStateError(
            f"reasoning verb 'critique' produced {type(artifact).__name__}, not a CritiqueArtifact"
        )

    concerns = len(artifact.concerns)
    if concerns:
        return ("objection" if seat_index == 0 else "challenge"), concerns
    if artifact.questions:
        return "clarification", len(artifact.questions)
    if seat_index == 0 and round_index > 1:
        return "response", 0
    return "support", 0


# --- convergence --------------------------------------------------------------------------------


@dataclass(frozen=True)
class ConvergenceVerdict:
    converged: bool
    reason: str
    unresolved: int


def evaluate_convergence(round_turns: list[dict[str, Any]]) -> ConvergenceVerdict:
    """Has the completed round left anything unresolved?

    The minimum signal M3.3 needs, and no more: a round converges when every turn in it was
    recorded and none of them still holds something against the standing proposal. It says
    "there is enough structured input to proceed to M3.4" -- not that a decision was made, and
    not that anyone approved anything.

    Note what this deliberately does NOT do: it never consults the round number. Under the default
    mock provider every critique carries a standing concern by construction, so a mock-mode
    discussion runs to its round limit and closes ``exhausted`` -- honestly, because a deterministic
    generator has not agreed to anything.
    """
    if not round_turns:
        return ConvergenceVerdict(False, "no turns recorded in this round", 0)

    incomplete = [t for t in round_turns if t.get("status") != "recorded"]
    if incomplete:
        return ConvergenceVerdict(False, f"{len(incomplete)} turn(s) not recorded", 0)

    proposals = [t for t in round_turns if t.get("intent") == "proposal"]
    unresolved = sum(
        int(t.get("concern_count") or 0)
        for t in round_turns
        if t.get("intent") in UNRESOLVED_INTENTS
    )
    if unresolved:
        return ConvergenceVerdict(
            False, f"{unresolved} unresolved concern(s)/question(s) remain", unresolved
        )

    has_standing_proposal = bool(proposals) or any(
        t.get("intent") in ("response", "support", "observation") for t in round_turns
    )
    if not has_standing_proposal:
        return ConvergenceVerdict(False, "no proposal is standing to converge on", 0)

    return ConvergenceVerdict(True, "no unresolved concern remains on the standing proposal", 0)


# --- bounded reasoning context ------------------------------------------------------------------

#: Hard caps on what any single reasoning turn is shown. Bounded deterministically rather than by
#: token estimate, so the same discussion state always produces the same context.
MAX_CONTEXT_MESSAGES = 6
MAX_CONTEXT_LIST_ITEMS = 5
MAX_CONTEXT_STEPS = 10
MAX_CONTEXT_TEXT = 1000


def _clip(value: Any, limit: int = MAX_CONTEXT_TEXT) -> str:
    return str(value or "")[:limit]


def _clip_list(values: Any, limit: int) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(_clip(v, 300) for v in values[:limit])


def build_turn_context(
    *,
    topic: str,
    round_index: int,
    goal: dict[str, Any],
    plan_revision: dict[str, Any] | None,
    recent_messages: list[dict[str, Any]],
    speaker: dict[str, Any],
    standing_proposal_summary: str | None,
) -> dict[str, Any]:
    """Assemble one turn's reasoning input from approved durable artifacts only.

    Only the Goal, the current PlanRevision's structured plan, recent TeamMessage summaries, the
    speaker's own participation metadata and the explicit discussion question. Never unrestricted
    repository or database state, and never anything a message body did not already say.

    The result is handed to AT-M3.1 in memory. ``ReasoningRequest.context`` is not persisted by
    that module, and nothing here writes it either.
    """
    plan = (plan_revision or {}).get("plan") or {}
    steps = plan.get("steps") if isinstance(plan, dict) else None

    context: dict[str, Any] = {
        "topic": _clip(topic),
        "round": round_index,
        "goal_statement": _clip(goal.get("statement")),
        "goal_acceptance_criteria": _clip_list(
            goal.get("acceptance_criteria"), MAX_CONTEXT_LIST_ITEMS
        ),
        "goal_constraints": _clip_list(goal.get("constraints"), MAX_CONTEXT_LIST_ITEMS),
        "speaker_role": _clip(speaker.get("functional_role"), 200),
        "speaker_capabilities": _clip_list(speaker.get("matched_capabilities"), 10),
        "recent_messages": [
            {
                "message_type": _clip(m.get("message_type"), 60),
                "summary": _clip(m.get("summary"), 400),
            }
            for m in recent_messages[-MAX_CONTEXT_MESSAGES:]
        ],
    }
    if plan_revision:
        context["plan_revision_number"] = plan_revision.get("revision_number")
        context["plan_objective"] = _clip(plan.get("objective") if isinstance(plan, dict) else "")
        context["plan_step_titles"] = tuple(
            _clip(s.get("title"), 200)
            for s in (steps or [])[:MAX_CONTEXT_STEPS]
            if isinstance(s, dict)
        )
    if standing_proposal_summary:
        context["proposal_summary"] = _clip(standing_proposal_summary, 400)
    return context


__all__ = [
    "DISCUSSION_STATES",
    "MAX_CONTEXT_MESSAGES",
    "MESSAGE_TYPE_FOR_INTENT",
    "MIN_PARTICIPANTS",
    "STATE_FOR_STOP_REASON",
    "UNRESOLVED_INTENTS",
    "ConvergenceVerdict",
    "DiscussionBounds",
    "DiscussionBoundsError",
    "DiscussionParticipant",
    "DiscussionParticipantError",
    "DiscussionSession",
    "DiscussionState",
    "DiscussionStateError",
    "DiscussionTurn",
    "DiscussionTurnLost",
    "DiscussionTurnUnresolvable",
    "StopReason",
    "TurnIntent",
    "TurnPlan",
    "TurnStatus",
    "build_turn_context",
    "classify_intent",
    "derive_correlation_id",
    "derive_idempotency_key",
    "evaluate_convergence",
    "plan_turn",
    "summary_seat",
]
