"""Step AT-M3.4 -- formalizing a converged discussion into a planning decision.

Pure. No I/O, so admissibility, the decision's content and the outcome are functions of rows
already read, and the same rows always produce the same decision.

Four boundaries this module exists to keep:

* **The plan is not the caller's.** AT-M3.4 Validation 1 showed what happened when it was: two
  callers racing one converged discussion with different plans, and commit ordering deciding which
  became "what the team selected". The plan is now authored by the routed planner principal through
  the AT-M3.1 ``decompose_plan`` verb, stored as a durable ``proposal`` TeamMessage, and read back
  from that message by :func:`plan_from_candidate`. There is no plan parameter left to substitute.
* **No new Proposal or Challenge entity.** The approved architecture's lineage matrix
  (``source-of-truth-and-lineage-model.md`` section 2) enumerates every entity in this model and
  contains neither. ``collaboration-and-workroom-model.md`` section 6 defines propose / challenge /
  converge as MESSAGE TYPES over ``ConversationThread``/``TeamMessage``, and section 7 puts the
  formal record of alternatives and dissent inside ``TeamDecision`` itself. The candidate plan is
  stored the same way, for the same reason.
* **A TeamDecision is not an Approval.** AT-ADR-06 / INV-03, restated by AT-D14 section 4: it is a
  team coordination artifact and never a substitute for a human Approval or a ProductOwnerDecision.
  Nothing here reads, writes or satisfies an approval record.
* **The outcome is derived, never requested.** :func:`derive_case` compares the candidate against
  what the Goal already has. A team that changed nothing gets a decision that says so, instead of a
  superseding revision holding an identical plan.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from shared.sdk.agent_planning.models import PlanContent

# --- vocabulary ---------------------------------------------------------------------------------

#: The two outcomes M3.4 produces, and the reason there are exactly two.
#:
#: The input gate admits ONLY a converged discussion; the planner then produces one candidate plan;
#: and that plan either differs from what the Goal already has or it does not. Nothing else is
#: reachable. ``rejected`` / ``deferred`` / ``unresolved`` are absent because no approved
#: architecture defines them, and migration 040's CHECK says the same thing, so adding one later
#: costs a migration and a decision.
PlanningOutcome = Literal["plan_accepted", "no_change"]
PLAN_ACCEPTED = "plan_accepted"
NO_CHANGE = "no_change"

#: Which of the four situations a finalization is in. The outcome above is what gets recorded; this
#: is what the writer needs to know in order to record it, and the two are not the same thing --
#: three distinct cases all record ``plan_accepted``, and they differ in what they write.
PlanningCase = Literal["initial_plan", "changed_plan", "accept_current_draft", "no_change"]
CASE_INITIAL = "initial_plan"
CASE_CHANGED = "changed_plan"
CASE_ACCEPT_DRAFT = "accept_current_draft"
CASE_NO_CHANGE = "no_change"

OUTCOME_FOR_CASE: dict[str, str] = {
    CASE_INITIAL: PLAN_ACCEPTED,
    CASE_CHANGED: PLAN_ACCEPTED,
    CASE_ACCEPT_DRAFT: PLAN_ACCEPTED,
    CASE_NO_CHANGE: NO_CHANGE,
}

#: The PlanRevision ``reason`` a plan change writes. Named by planning-and-plan-revision-model.md
#: section 5 as the trigger for "the team chose a different approach", which is exactly this.
REVISION_REASON = "team_decision"

#: The AT-M3.1 verb that authors the candidate plan, and the capability its author must hold.
PLANNER_VERB = "decompose_plan"
PLANNER_CAPABILITY = "plan_project"

#: AT-M2 message types that carry the deliberation behind a decision. Read as evidence, never
#: rewritten: ``proposal`` is what was put on the table, ``challenge`` is what was said against it.
#:
#: The planner's structured candidate plan is a ``proposal`` too, and deliberately not a ``replan``:
#: collaboration-and-workroom-model.md section 5 defines ``replan`` as state-changing -- "yes, new
#: PlanRevision" -- and a candidate may exist and never produce one, because the finalization may
#: go stale, may fail, or may conclude no_change. A durable message must not assert what did not
#: happen. Candidates are told apart from deliberation proposals by the marker below, which is an
#: exact reference and not a guess about shape.
PROPOSAL_MESSAGE_TYPE = "proposal"
CHALLENGE_MESSAGE_TYPE = "challenge"

#: The ``artifact_refs`` key that makes a message THE candidate plan for a specific discussion.
CANDIDATE_REF_KEY = "candidate_plan_for_discussion"

#: Turn intents that mean the speaker was still holding something against the standing proposal.
#: Mirrors AT-M3.3's ``UNRESOLVED_INTENTS``; carried here so a dissent summary can name what was
#: outstanding when the room converged rather than asserting there was nothing.
UNRESOLVED_TURN_INTENTS: frozenset[str] = frozenset({"challenge", "objection", "clarification"})

#: What an admissible discussion must look like. Every clause is checked against durable rows, and
#: the currency clause is checked TWICE -- here for a clear error, and again under ``FOR UPDATE``
#: inside the writing transaction, which is the clause that actually protects the plan.
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


class PlanningDecisionConflictError(ValueError):
    """Another finalization holds the ground this one needs, and it is not this discussion's own.

    Distinct from a replay: a replay means *this* discussion was already formalized and the answer
    is its result. This means something else got there -- a different discussion accepted the same
    revision, or the worker that claimed this discussion's candidate has not finished. Neither is a
    fault the caller can fix by retrying immediately, and neither is a server error.
    """


class PlannerUnavailableError(ValueError):
    """No principal on this team can author a plan, so no plan is authored.

    Fail closed rather than letting the caller nominate one: a decision attributed to a principal
    that did not do the work is worse than no decision.
    """


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
    and the write. AT-M3.2 re-checks it under ``FOR UPDATE`` inside the same transaction that
    writes -- ``create_successor_revision`` when the plan changes, ``confirm_current_revision``
    when it does not -- and that is what actually holds.
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


# --- the candidate plan ---------------------------------------------------------------------------


def is_candidate_for(message: dict[str, Any], discussion_id: Any) -> bool:
    """Is this message THE planner's candidate plan for that discussion?

    Answered from an explicit reference the planner wrote, never from the shape of the content. A
    deliberation proposal and a candidate plan are both ``proposal`` messages; guessing which is
    which by sniffing for a ``plan`` key would make an unrelated message substitutable.
    """
    refs = message.get("artifact_refs") or {}
    if not isinstance(refs, dict):
        return False
    return (
        message.get("message_type") == PROPOSAL_MESSAGE_TYPE
        and str(refs.get(CANDIDATE_REF_KEY) or "") == str(discussion_id)
    )


def plan_from_candidate(message: dict[str, Any]) -> dict[str, Any]:
    """The structured plan the candidate message carries, validated through AT-M3.2's own schema.

    Routed through ``PlanContent`` rather than trusted: the message was written by this service, but
    reading it back through the canonical model is what guarantees the revision and the candidate
    hold the same shape, and it is the same validation a reviewer would apply. A candidate that
    cannot be parsed is a refusal, never a silently-empty plan.
    """
    content = message.get("content") or {}
    if not isinstance(content, dict) or not isinstance(content.get("plan"), dict):
        raise PlanningDecisionStateError(
            f"candidate message {message.get('message_id')} carries no structured plan"
        )
    return PlanContent(**content["plan"]).model_dump(mode="json")


def derive_case(
    *, current_revision: dict[str, Any] | None, candidate_plan: dict[str, Any]
) -> str:
    """Which of the four situations this finalization is in. Server-side, from durable rows only.

    ```text
    no current revision                          initial_plan          root created and accepted
    candidate differs from current               changed_plan          successor created, accepted
    candidate identical, current is 'draft'      accept_current_draft  that same revision accepted
    candidate identical, current is 'accepted'   no_change             nothing written to the plan
    ```

    The third case is why "identical" is not simply "no decision to make": a Goal can hold a draft
    revision that no team has ever formally accepted, and a decision confirming it is a real
    acceptance -- it just does not need a new revision to express one.

    A predecessor whose stored plan does not parse as ``PlanContent`` counts as *different*. The
    store accepts a plan as raw JSON, so such a row is reachable; treating an unreadable plan as
    equal to anything would be the one wrong answer.
    """
    if current_revision is None:
        return CASE_INITIAL

    try:
        before = PlanContent(**(current_revision.get("plan") or {}))
    except Exception:
        return CASE_CHANGED

    if before != PlanContent(**candidate_plan):
        return CASE_CHANGED

    status = current_revision.get("status")
    if status == "draft":
        return CASE_ACCEPT_DRAFT
    if status == "accepted":
        return CASE_NO_CHANGE
    raise PlanningDecisionStateError(
        f"revision {current_revision.get('plan_revision_id')} is '{status}'; AT-M3.2 authorizes no "
        "transition out of it, so no planning decision can be recorded against it"
    )


# --- deterministic formalization ------------------------------------------------------------------


class DecisionEvidence(BaseModel):
    """What the team said, reduced to the three fields the TeamDecision contract names.

    Read from the discussion's own convergence summary and its proposal/challenge messages. Nothing
    is generated: ``options_considered``, ``selected_option`` and ``dissent_summary`` come from a
    ``DecisionSummaryArtifact`` AT-M3.3 already persisted.
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
    discussion_id: Any,
) -> DecisionEvidence:
    """Turn the discussion's durable record into the formal decision's content.

    The convergence summary supplies the selection and the rationale. The thread's proposal and
    challenge messages supply the alternatives and the identifiers that let a reader walk back from
    the decision to what was actually said. The planner's own candidate message is excluded from
    the deliberation evidence -- it is the plan the decision selected, not one of the options the
    room weighed, and counting it as both would double-count it.

    Dissent is DERIVED, not asserted. If the summary named dissent it is carried through verbatim;
    otherwise any turn still holding a concern when the round closed is counted, and the count is
    reported rather than a claim that nothing was outstanding. A decision that hides disagreement is
    worse than no record (collaboration-and-workroom-model.md section 6).
    """
    content = result_message.get("content") or {}
    if not isinstance(content, dict):
        content = {}

    deliberation = [m for m in messages if not is_candidate_for(m, discussion_id)]

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
            for m in deliberation
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
            str(m["message_id"])
            for m in deliberation
            if m.get("message_type") == PROPOSAL_MESSAGE_TYPE
        ),
        challenge_message_ids=tuple(
            str(m["message_id"])
            for m in deliberation
            if m.get("message_type") == CHALLENGE_MESSAGE_TYPE
        ),
    )


def derive_idempotency_key(*, discussion_id: Any, result_message_id: Any) -> str:
    """The finalization identity, bound to the discussion and the exact evidence it produced.

    Derived rather than random so a retry of the same command resolves to the same row without the
    caller having to remember a token. The discussion id alone would do -- it is UNIQUE on the
    ledger -- but binding the result message too means a key can never outlive the evidence it
    claims to be about. The candidate plan is deliberately NOT in the key: one discussion can only
    ever have one candidate, so including it would add a component that never varies.
    """
    raw = f"{discussion_id}|{result_message_id}"
    return "m34:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def derive_candidate_correlation_id(*, discussion_id: Any, result_message_id: Any) -> str:
    """The AT-M3.1 correlation id for this discussion's one and only planning call.

    A UUID derived from the discussion, so ``uq_reasoning_invocations_correlation`` is what makes
    "one ``decompose_plan`` invocation per discussion" true at the database layer rather than by
    convention. Eight workers finalizing one discussion claim the same id; one wins.
    """
    digest = hashlib.sha256(
        f"m34-candidate|{discussion_id}|{result_message_id}".encode()
    ).hexdigest()
    return (
        f"{digest[0:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
    )


__all__ = [
    "ADMISSIBLE_STATE",
    "ADMISSIBLE_STOP_REASON",
    "CANDIDATE_REF_KEY",
    "CASE_ACCEPT_DRAFT",
    "CASE_CHANGED",
    "CASE_INITIAL",
    "CASE_NO_CHANGE",
    "CHALLENGE_MESSAGE_TYPE",
    "NO_CHANGE",
    "OUTCOME_FOR_CASE",
    "PLANNER_CAPABILITY",
    "PLANNER_VERB",
    "PLAN_ACCEPTED",
    "PROPOSAL_MESSAGE_TYPE",
    "REVISION_REASON",
    "UNRESOLVED_TURN_INTENTS",
    "AdmissibilityVerdict",
    "DecisionEvidence",
    "DiscussionNotAdmissibleError",
    "PlannerUnavailableError",
    "PlanningCase",
    "PlanningDecisionConflictError",
    "PlanningDecisionStateError",
    "PlanningOutcome",
    "build_decision_evidence",
    "derive_candidate_correlation_id",
    "derive_case",
    "derive_idempotency_key",
    "evaluate_admissibility",
    "is_candidate_for",
    "plan_from_candidate",
]
