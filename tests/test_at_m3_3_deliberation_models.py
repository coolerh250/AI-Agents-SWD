"""Step AT-M3.3 -- the pure deliberation logic: turn planning, intent, convergence, context.

No database and no provider. Everything asserted here is a function of its inputs, which is the
property that lets a resumed process in another operating-system process reach the same next turn
from the same durable rows.
"""

from __future__ import annotations

import pytest

from shared.sdk.agent_deliberation.models import (
    MESSAGE_TYPE_FOR_INTENT,
    MIN_PARTICIPANTS,
    BOUND_STOP_REASONS,
    STATE_FOR_STOP_REASON,
    STOP_REASON_FOR_BOUND,
    STOP_REASON_PRECEDENCE,
    UNRESOLVED_INTENTS,
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
from shared.sdk.agent_reasoning.models import (
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ProposalArtifact,
)


def _proposal() -> ProposalArtifact:
    return ProposalArtifact(
        summary="ship the smallest viable slice",
        rationale_summary="it is the only part the goal actually requires",
        recommendation="start with the API contract",
    )


def _critique(
    *, concerns: tuple[str, ...] = (), questions: tuple[str, ...] = ()
) -> CritiqueArtifact:
    return CritiqueArtifact(
        summary="review of the standing proposal",
        rationale_summary="assessed against the goal's acceptance criteria",
        concerns=concerns,
        questions=questions,
        recommendation="proceed" if not concerns else "revise",
    )


# --- turn planning ------------------------------------------------------------------------------


def test_seat_zero_proposes_in_round_one_and_responds_afterwards():
    assert plan_turn(1, 0, 3).reasoning_verb == "propose"
    assert plan_turn(2, 0, 3).reasoning_verb == "critique"
    assert plan_turn(7, 0, 3).reasoning_verb == "critique"


def test_seat_zero_addresses_the_team_and_everyone_else_addresses_seat_zero():
    opener = plan_turn(1, 0, 3)
    assert opener.addresses_team is True
    assert opener.addresses_seat is None
    for seat in (1, 2):
        reply = plan_turn(1, seat, 3)
        assert reply.addresses_team is False
        assert reply.addresses_seat == 0, "a critique nobody is asked to answer is not deliberation"


def test_turn_planning_is_deterministic():
    assert plan_turn(2, 1, 4) == plan_turn(2, 1, 4)


def test_a_monologue_is_not_a_discussion():
    with pytest.raises(DiscussionParticipantError):
        plan_turn(1, 0, 1)
    assert MIN_PARTICIPANTS == 2


def test_the_summary_turn_sits_past_the_last_participant():
    # It must not collide with any participant's slot, and must not consume a participant budget.
    assert summary_seat(3) == 3
    assert summary_seat(2) == 2


# --- intent classification ----------------------------------------------------------------------


def test_propose_is_always_a_proposal():
    intent, concerns = classify_intent(
        reasoning_verb="propose", artifact=_proposal(), seat_index=0, round_index=1
    )
    assert (intent, concerns) == ("proposal", 0)


def test_a_critique_with_concerns_is_a_challenge_and_carries_its_count():
    intent, concerns = classify_intent(
        reasoning_verb="critique",
        artifact=_critique(concerns=("scope is wrong", "no rollback")),
        seat_index=2,
        round_index=1,
    )
    assert intent == "challenge"
    assert concerns == 2


def test_seat_zero_raising_concerns_is_an_objection_not_a_challenge():
    # Seat 0 owns the standing proposal; when it raises concerns it is objecting to the round's
    # critiques, not critiquing a peer.
    intent, _ = classify_intent(
        reasoning_verb="critique", artifact=_critique(concerns=("x",)), seat_index=0, round_index=2
    )
    assert intent == "objection"


def test_questions_without_concerns_are_a_clarification_and_still_count_as_unresolved():
    intent, count = classify_intent(
        reasoning_verb="critique",
        artifact=_critique(questions=("which environment?",)),
        seat_index=1,
        round_index=1,
    )
    assert intent == "clarification"
    assert count == 1
    assert intent in UNRESOLVED_INTENTS


def test_a_clean_critique_is_support():
    intent, count = classify_intent(
        reasoning_verb="critique", artifact=_critique(), seat_index=1, round_index=1
    )
    assert (intent, count) == ("support", 0)


def test_seat_zero_with_nothing_outstanding_is_a_response():
    intent, _ = classify_intent(
        reasoning_verb="critique", artifact=_critique(), seat_index=0, round_index=2
    )
    assert intent == "response"


def test_summarize_decision_is_the_convergence_summary():
    artifact = DecisionSummaryArtifact(
        summary="where the team got to",
        rationale_summary="no concern is outstanding",
        options_considered=("a", "b"),
        selected_option="a",
    )
    intent, _ = classify_intent(
        reasoning_verb="summarize_decision", artifact=artifact, seat_index=0, round_index=2
    )
    assert intent == "convergence_summary"


def test_a_verb_and_artifact_that_disagree_fail_closed():
    with pytest.raises(DiscussionStateError):
        classify_intent(
            reasoning_verb="critique", artifact=_proposal(), seat_index=1, round_index=1
        )


# --- the AT-M2 message vocabulary is not widened --------------------------------------------------


def test_every_intent_maps_onto_an_existing_team_message_type():
    # AT-D14 pre-cleared exactly one alteration of an AT-M2 table and this is not it, so the
    # discussion's own vocabulary must land inside the collaboration contract's existing types.
    allowed = {
        "message",
        "proposal",
        "challenge",
        "decision_summary",
        "handoff",
        "blocker",
        "clarification_question",
        "clarification_answer",
        "debug_hypothesis",
        "debug_result",
        "replan",
        "system_event",
        "audit_event",
    }
    assert set(MESSAGE_TYPE_FOR_INTENT.values()) <= allowed


def test_the_convergence_summary_is_not_posted_as_a_decision_summary():
    # decision_summary "points at a TeamDecision" and changes state. M3.3 records no TeamDecision,
    # so posting one would announce a decision that does not exist.
    assert MESSAGE_TYPE_FOR_INTENT["convergence_summary"] == "message"
    assert "decision_summary" not in MESSAGE_TYPE_FOR_INTENT.values()


# --- convergence --------------------------------------------------------------------------------


def _turn(intent: str, concerns: int = 0, status: str = "recorded", seat: int = 0) -> dict:
    return {"intent": intent, "concern_count": concerns, "status": status, "seat_index": seat}


def test_a_round_with_no_unresolved_concern_converges():
    verdict = evaluate_convergence(
        [_turn("proposal", seat=0), _turn("support", seat=1), _turn("support", seat=2)]
    )
    assert verdict.converged is True
    assert verdict.unresolved == 0


def test_a_single_outstanding_concern_prevents_convergence():
    verdict = evaluate_convergence(
        [_turn("proposal", seat=0), _turn("support", seat=1), _turn("challenge", 1, seat=2)]
    )
    assert verdict.converged is False
    assert verdict.unresolved == 1


def test_an_outstanding_question_also_prevents_convergence():
    verdict = evaluate_convergence([_turn("proposal"), _turn("clarification", 1, seat=1)])
    assert verdict.converged is False


def test_an_incomplete_round_never_converges():
    verdict = evaluate_convergence([_turn("proposal"), _turn("support", status="claimed", seat=1)])
    assert verdict.converged is False
    assert "not recorded" in verdict.reason


def test_an_empty_round_never_converges():
    assert evaluate_convergence([]).converged is False


def test_convergence_never_consults_the_round_number():
    # The signal is a function of what was said. There is no argument through which the number of
    # elapsed rounds could reach it, which is what stops exhaustion being reported as consensus.
    import inspect

    signature = inspect.signature(evaluate_convergence)
    assert list(signature.parameters) == ["round_turns"]


# --- state / stop reason separation ---------------------------------------------------------------


def test_running_out_of_rounds_can_never_be_recorded_as_converged():
    assert STATE_FOR_STOP_REASON["round_limit_reached"] == "exhausted"
    assert STATE_FOR_STOP_REASON["message_limit_reached"] == "exhausted"
    assert STATE_FOR_STOP_REASON["invocation_limit_reached"] == "exhausted"
    assert STATE_FOR_STOP_REASON["participant_turn_limit_reached"] == "exhausted"
    assert STATE_FOR_STOP_REASON["timeout_reached"] == "exhausted"
    assert STATE_FOR_STOP_REASON["convergence_reached"] == "converged"


def test_every_failure_reason_lands_in_a_failed_state():
    for reason in (
        "participant_unavailable",
        "reasoning_provider_failure",
        "insufficient_capability_coverage",
        "insufficient_participants",
    ):
        assert STATE_FOR_STOP_REASON[reason] == "failed"


def test_each_of_the_five_bounds_has_its_own_stop_reason():
    """One bound, one reason. A reason shared between two bounds is a reason that misleads."""
    assert set(STOP_REASON_FOR_BOUND) == {
        "max_rounds",
        "max_messages",
        "max_invocations",
        "max_turns_per_participant",
        "deadline_at",
    }
    assert len(set(STOP_REASON_FOR_BOUND.values())) == len(STOP_REASON_FOR_BOUND)
    # The two the remediation separated out, named explicitly so a future merge cannot quietly
    # collapse them back into their neighbours.
    assert STOP_REASON_FOR_BOUND["max_turns_per_participant"] == "participant_turn_limit_reached"
    assert STOP_REASON_FOR_BOUND["deadline_at"] == "timeout_reached"
    assert STOP_REASON_FOR_BOUND["max_rounds"] == "round_limit_reached"


def test_a_participant_count_failure_is_not_a_capability_failure():
    """Different facts, different repairs: add a capability, or add an agent."""
    assert "insufficient_participants" in STATE_FOR_STOP_REASON
    assert "insufficient_capability_coverage" in STATE_FOR_STOP_REASON
    assert (
        STATE_FOR_STOP_REASON["insufficient_participants"]
        != "exhausted"  # both are failures, not exhaustion
    )


def test_the_wall_clock_outranks_every_count_bound():
    """Precedence is declared, not left to whichever check happens to run first."""
    assert STOP_REASON_PRECEDENCE[0] == "timeout_reached"
    assert set(STOP_REASON_PRECEDENCE) <= set(STATE_FOR_STOP_REASON)
    assert len(set(STOP_REASON_PRECEDENCE)) == len(STOP_REASON_PRECEDENCE)
    # Every count bound appears, so no bound can fire without a declared position.
    assert set(BOUND_STOP_REASONS) <= set(STOP_REASON_PRECEDENCE)


def test_the_timeout_bound_is_persisted_alongside_the_counts():
    bounds = DiscussionBounds()
    assert bounds.timeout_seconds > 0
    assert "timeout_seconds" in bounds.model_dump()
    with pytest.raises(Exception):
        DiscussionBounds(timeout_seconds=0)
    with pytest.raises(Exception):
        DiscussionBounds(timeout_seconds=86401)
    # Fractional, so a test can bound a discussion in under a second without a second notion of
    # "how long" existing in the runtime.
    assert DiscussionBounds(timeout_seconds=0.25).timeout_seconds == 0.25


def test_only_convergence_maps_to_converged():
    converging = [r for r, s in STATE_FOR_STOP_REASON.items() if s == "converged"]
    assert converging == ["convergence_reached"]


# --- deterministic identity -----------------------------------------------------------------------


def test_a_turn_slot_always_derives_the_same_correlation_id():
    first = derive_correlation_id("d1", 2, 1)
    assert first == derive_correlation_id("d1", 2, 1)
    assert first != derive_correlation_id("d1", 2, 2)
    assert first != derive_correlation_id("d2", 2, 1)


def test_the_same_start_request_derives_the_same_idempotency_key():
    args = {"project_id": "p", "goal_id": "g", "plan_revision_id": "r", "topic": " ship it "}
    assert derive_idempotency_key(**args) == derive_idempotency_key(**args)
    assert derive_idempotency_key(**{**args, "topic": "ship it"}) == derive_idempotency_key(**args)
    assert derive_idempotency_key(**{**args, "topic": "other"}) != derive_idempotency_key(**args)


# --- bounds ---------------------------------------------------------------------------------------


def test_bounds_are_closed_and_defaulted():
    bounds = DiscussionBounds()
    assert bounds.max_rounds >= 1 and bounds.max_messages >= 1
    with pytest.raises(Exception):
        DiscussionBounds(max_rounds=0)
    with pytest.raises(Exception):
        DiscussionBounds(unbounded=True)


# --- bounded context ------------------------------------------------------------------------------


def test_context_is_bounded_and_carries_only_approved_artifacts():
    context = build_turn_context(
        topic="t" * 5000,
        round_index=2,
        goal={
            "statement": "s" * 5000,
            "acceptance_criteria": [f"c{i}" for i in range(50)],
            "constraints": [f"k{i}" for i in range(50)],
        },
        plan_revision={
            "revision_number": 4,
            "plan": {
                "objective": "o" * 5000,
                "steps": [{"title": f"step {i}"} for i in range(50)],
            },
        },
        recent_messages=[
            {"message_type": "message", "summary": f"m{i}", "content": {"secret": "x"}}
            for i in range(50)
        ],
        speaker={"functional_role": "qa", "matched_capabilities": ["verify_quality"]},
        standing_proposal_summary="the standing proposal",
    )
    assert len(context["topic"]) <= 1000
    assert len(context["goal_statement"]) <= 1000
    assert len(context["goal_acceptance_criteria"]) <= 5
    assert len(context["goal_constraints"]) <= 5
    assert len(context["plan_step_titles"]) <= 10
    assert len(context["recent_messages"]) <= 6
    # Only the two safe message fields travel; a message BODY is not context.
    assert all(set(m) == {"message_type", "summary"} for m in context["recent_messages"])


def test_context_omits_plan_fields_when_the_goal_has_no_revision_yet():
    context = build_turn_context(
        topic="what should the first plan be",
        round_index=1,
        goal={"statement": "ship"},
        plan_revision=None,
        recent_messages=[],
        speaker={"functional_role": "planner", "matched_capabilities": []},
        standing_proposal_summary=None,
    )
    assert "plan_revision_number" not in context
    assert "proposal_summary" not in context


def test_the_assembled_context_passes_the_reasoning_contract_content_screen():
    from shared.sdk.agent_reasoning.models import ReasoningRequest

    context = build_turn_context(
        topic="scope",
        round_index=1,
        goal={"statement": "ship", "acceptance_criteria": ["works"], "constraints": []},
        plan_revision=None,
        recent_messages=[{"message_type": "proposal", "summary": "do the thing"}],
        speaker={"functional_role": "planner", "matched_capabilities": ["plan_project"]},
        standing_proposal_summary="do the thing",
    )
    # Constructing the request runs assert_content_is_safe over the whole context.
    request = ReasoningRequest(verb="propose", context=context)
    assert request.context["topic"] == "scope"
