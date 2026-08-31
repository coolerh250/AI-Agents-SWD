"""Step AT-M3.4 -- formalizing a converged discussion into a planning decision.

Pure. No I/O, so admissibility and the decision's content are functions of rows already read, and
the same rows always produce the same decision.

Three boundaries this module exists to keep:

* **No new Proposal or Challenge entity.** The approved architecture's lineage matrix
  (``source-of-truth-and-lineage-model.md`` section 2) enumerates every entity in this model and
  contains neither. ``collaboration-and-workroom-model.md`` section 6 defines propose / challenge /
  converge as MESSAGE TYPES over ``ConversationThread``/``TeamMessage``, and section 7 puts the
  formal record of alternatives and dissent inside ``TeamDecision`` itself. A proposal is therefore
  already durable and already structured -- a TeamMessage of type ``proposal`` plus the AT-M3.3
  turn-ledger entry that says which turn produced it. Building tables for them would invent
  entities the architecture declined to define and give one deliberation two competing records.
* **A TeamDecision is not an Approval.** AT-ADR-06 / INV-03, restated by AT-D14 section 4: it is a
  team coordination artifact and never a substitute for a human Approval or a ProductOwnerDecision.
  Nothing here reads, writes or satisfies an approval record.
* **Formalization is deterministic.** ``DecisionSummaryArtifact`` already carries
  ``options_considered``, ``selected_option`` and ``dissent_summary`` -- the exact three fields the
  TeamDecision contract names. The discussion's structured result therefore already IS the decision
  evidence, so M3.4 reads it rather than calling a provider to re-derive it. No reasoning
  invocation happens in this slice.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from shared.sdk.agent_planning.models import PlanContent

# --- vocabulary ---------------------------------------------------------------------------------

#: The one outcome M3.4 produces, and the reason there is only one.
#:
#: The input gate admits ONLY a converged discussion, and convergence is precisely "the team has
#: something to accept". The architecture does permit a TeamDecision that changes no plan --
#: ``resulting_plan_revision_id`` is nullable in collaboration-and-workroom-model.md section 7 --
#: but no admissible M3.4 input can reach that state, so no code here manufactures one. Migration
#: 040's CHECK says the same thing, so a second outcome costs a migration and a decision.
PlanningOutcome = Literal["plan_accepted"]
PLAN_ACCEPTED = "plan_accepted"

#: The PlanRevision ``reason`` this path writes. Named by planning-and-plan-revision-model.md
#: section 5 as the trigger for "the team chose a different approach", which is exactly this.
REVISION_REASON = "team_decision"

#: AT-M2 message types that carry the deliberation behind a decision. Read as evidence, never
#: rewritten: ``proposal`` is what was put on the table, ``challenge`` is what was said against it.
PROPOSAL_MESSAGE_TYPE = "proposal"
CHALLENGE_MESSAGE_TYPE = "challenge"

#: Turn intents that mean the speaker was still holding something against the standing proposal.
#: Mirrors AT-M3.3's ``UNRESOLVED_INTENTS``; carried here so a dissent summary can name what was
#: outstanding when the room converged rather than asserting there was nothing.
UNRESOLVED_TURN_INTENTS: frozenset[str] = frozenset({"challenge", "objection", "clarification"})

#: What an admissible discussion must look like. Every clause is checked against durable rows, and
#: the currency clause is checked TWICE -- here for a clear error, and again by AT-M3.2's
#: compare-and-swap at the moment of writing, which is the clause that actually protects the plan.
ADMISSIBLE_STATE = "converged"
ADMISSIBLE_STOP_REASON = "convergence_reached"


# --- errors -------------------------------------------------------------------------------------


class DiscussionNotAdmissibleError(ValueError):
    """The discussion cannot be consumed as planning evidence, and says exactly which clause failed.

    A single error type with a precise message rather than six types: every one of these is the
    same fact from the caller's side -- this discussion is not a decision input -- and the useful
    difference is which clause, which the message carries.
    """

    def __init__(self, discussion_id: Any, clause: str, detail: str) -> None:
        self.discussion_id = str(discussion_id)
        self.clause = clause
        super().__init__(f"discussion {discussion_id} is not admissible ({clause}): {detail}")


class PlanningDecisionStateError(ValueError):
    """An operation that is not legal against the current planning-decision state."""


# --- admissibility ------------------------------------------------------------------------------


@dataclass(frozen=True)
class AdmissibilityVerdict:
    admissible: bool
    clause: str
    detail: str


def evaluate_admissibility(
    *,
    discussion: dict[str, Any] | None,
    goal_id: Any,
    current_plan_revision_id: Any,
) -> AdmissibilityVerdict:
    """Is this discussion consumable as planning evidence?

    Five clauses, checked in the order that makes the failure most useful to read: existence, then
    what the discussion IS, then what it produced, then what it was about, then whether the world
    has moved since.

    The last clause is the one that matters and the one that is NOT trusted. Currency here is a
    pre-read: it produces a clear error instead of an opaque constraint violation, and it is
    explicitly not the safety boundary, because the answer can stop being true between this check
    and the write. AT-M3.2's ``create_successor_revision`` re-checks it under ``FOR UPDATE`` inside
    the same transaction that writes, and that is what actually holds.
    """
    if discussion is None:
        return AdmissibilityVerdict(False, "exists", "no such discussion")

    state = discussion.get("state")
    if state != ADMISSIBLE_STATE:
        return AdmissibilityVerdict(
            False,
            "state",
            f"state is '{state}', not '{ADMISSIBLE_STATE}'; an exhausted, failed or cancelled "
            "deliberation reached no conclusion to formalize",
        )

    stop_reason = discussion.get("stop_reason")
    if stop_reason != ADMISSIBLE_STOP_REASON:
        return AdmissibilityVerdict(
            False,
            "stop_reason",
            f"stop reason is '{stop_reason}', not '{ADMISSIBLE_STOP_REASON}'",
        )

    if not discussion.get("result_message_id"):
        return AdmissibilityVerdict(
            False, "result", "converged with no result message; there is no evidence to consume"
        )

    if str(discussion.get("goal_id")) != str(goal_id):
        return AdmissibilityVerdict(
            False,
            "goal",
            f"discussion is about goal {discussion.get('goal_id')}, not {goal_id}",
        )

    bound = discussion.get("plan_revision_id")
    current = current_plan_revision_id
    if bound is None:
        if current is not None:
            return AdmissibilityVerdict(
                False,
                "currency",
                f"the discussion deliberated a goal with no plan, but revision {current} now "
                "exists; its premise no longer holds",
            )
        return AdmissibilityVerdict(True, "currency", "goal still has no plan")

    if current is None or str(bound) != str(current):
        return AdmissibilityVerdict(
            False,
            "currency",
            f"the discussion is bound to revision {bound}, which is no longer current "
            f"(current is {current}); it remains evidence about {bound} and is not rebound",
        )
    return AdmissibilityVerdict(True, "currency", "bound revision is still current")


# --- deterministic formalization ------------------------------------------------------------------


class DecisionEvidence(BaseModel):
    """What the team said, reduced to the three fields the TeamDecision contract names.

    Read from the discussion's own convergence summary and its proposal/challenge messages. Nothing
    is generated: ``options_considered``, ``selected_option`` and ``dissent_summary`` come from a
    ``DecisionSummaryArtifact`` AT-M3.3 already persisted, which is why M3.4 needs no provider.
    """

    model_config = ConfigDict(extra="forbid")

    selected_option: str = Field(min_length=1, max_length=500)
    options_considered: tuple[str, ...] = ()
    rationale_summary: str = Field(min_length=1, max_length=4000)
    dissent_summary: str | None = Field(default=None, max_length=2000)
    proposal_message_ids: tuple[str, ...] = ()
    challenge_message_ids: tuple[str, ...] = ()


def _clip(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def build_decision_evidence(
    *,
    result_message: dict[str, Any],
    messages: list[dict[str, Any]],
    turns: list[dict[str, Any]],
) -> DecisionEvidence:
    """Turn the discussion's durable record into the formal decision's content.

    The convergence summary supplies the selection and the rationale. The thread's proposal and
    challenge messages supply the alternatives and the identifiers that let a reader walk back from
    the decision to what was actually said.

    Dissent is DERIVED, not asserted. If the summary named dissent it is carried through verbatim;
    otherwise any turn still holding a concern when the round closed is counted, and the count is
    reported rather than a claim that nothing was outstanding. A decision that hides disagreement is
    worse than no record (collaboration-and-workroom-model.md section 6).
    """
    content = result_message.get("content") or {}
    if not isinstance(content, dict):
        content = {}

    selected = _clip(content.get("selected_option"), 500) or _clip(
        result_message.get("summary"), 500
    )
    rationale = _clip(content.get("rationale_summary"), 4000) or _clip(
        result_message.get("summary"), 4000
    )

    raw_options = content.get("options_considered")
    options = tuple(_clip(o, 500) for o in raw_options if _clip(o, 500)) if raw_options else ()
    if not options:
        # Fall back to what was actually proposed in the thread. Never an empty list: the contract
        # says a decision names the alternatives it considered.
        options = tuple(
            _clip(m.get("summary"), 500)
            for m in messages
            if m.get("message_type") == PROPOSAL_MESSAGE_TYPE and _clip(m.get("summary"), 500)
        )

    dissent = _clip(content.get("dissent_summary"), 2000) or None
    if dissent is None:
        outstanding = sum(
            int(t.get("concern_count") or 0)
            for t in turns
            if t.get("intent") in UNRESOLVED_TURN_INTENTS
        )
        if outstanding:
            dissent = (
                f"{outstanding} concern(s) or question(s) were raised during the deliberation and "
                "are recorded in the thread"
            )

    return DecisionEvidence(
        selected_option=selected or "proceed with the standing proposal",
        options_considered=options or (selected or "proceed with the standing proposal",),
        rationale_summary=rationale or "the team converged on the standing proposal",
        dissent_summary=dissent,
        proposal_message_ids=tuple(
            str(m["message_id"]) for m in messages if m.get("message_type") == PROPOSAL_MESSAGE_TYPE
        ),
        challenge_message_ids=tuple(
            str(m["message_id"])
            for m in messages
            if m.get("message_type") == CHALLENGE_MESSAGE_TYPE
        ),
    )


def derive_idempotency_key(*, discussion_id: Any, result_message_id: Any) -> str:
    """The finalization identity, bound to the discussion and the exact evidence it produced.

    Derived rather than random so a retry of the same command resolves to the same row without the
    caller having to remember a token. The discussion id alone would do -- it is UNIQUE on the
    ledger -- but binding the result message too means a key can never outlive the evidence it
    claims to be about.
    """
    raw = f"{discussion_id}|{result_message_id}"
    return "m34:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def validate_plan(plan: Any) -> dict[str, Any]:
    """Structure the caller's plan through the existing M3.2 schema, or refuse it.

    A plan reaches M3.4 as structured content and is stored as structured content. Prose is not a
    plan: ``PlanContent`` requires an objective, validates that every ``depends_on`` names a step
    that exists and that no step depends on itself, and screens the whole payload for forbidden
    keys. Routing it through the same model M3.2 uses means the successor is diffable against its
    predecessor by construction.

    M3.4 does not AUTHOR this content. No reasoning verb produces a plan -- ``propose``,
    ``critique`` and ``summarize_decision`` are the three AT-M3.1 defines -- so generating one would
    mean extending the M3.1 contract, which is its own authorization. Deterministic formalization
    of what the team decided is what this slice does; inventing the plan is not.
    """
    if isinstance(plan, PlanContent):
        return plan.model_dump(mode="json")
    if not isinstance(plan, dict):
        raise PlanningDecisionStateError(
            "a planning decision needs structured plan content, not "
            f"{type(plan).__name__}; prose is not a plan"
        )
    return PlanContent(**plan).model_dump(mode="json")


__all__ = [
    "ADMISSIBLE_STATE",
    "ADMISSIBLE_STOP_REASON",
    "CHALLENGE_MESSAGE_TYPE",
    "PLAN_ACCEPTED",
    "PROPOSAL_MESSAGE_TYPE",
    "REVISION_REASON",
    "UNRESOLVED_TURN_INTENTS",
    "AdmissibilityVerdict",
    "DecisionEvidence",
    "DiscussionNotAdmissibleError",
    "PlanningDecisionStateError",
    "PlanningOutcome",
    "build_decision_evidence",
    "derive_idempotency_key",
    "evaluate_admissibility",
    "validate_plan",
]
