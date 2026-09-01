"""Step AT-M3.4 -- the ``decompose_plan`` reasoning verb.

The AT-M3.1 contract shipped three verbs and all three return prose, which is why AT-M3.4 had no
way to produce a plan and ended up taking one from its caller. This is the verb that closes that,
and these are the properties it has to keep: a strict artifact carrying AT-M3.2's own
``PlanContent`` and no second plan schema, determinism strong enough for the M3.4 proofs to rest
on, and every existing AT-M3.1 invariant unchanged.
"""

from __future__ import annotations

import pytest

from shared.sdk.agent_planning.models import PlanContent
from shared.sdk.agent_reasoning.mock_provider import MockReasoningProvider
from shared.sdk.agent_reasoning.models import (
    ARTIFACT_TYPE_FOR_VERB,
    REASONING_VERBS,
    PlanDraftArtifact,
    ReasoningRequest,
)
from shared.sdk.agent_reasoning.provider import (
    DisabledReasoningProvider,
    ReasoningProviderError,
    get_reasoning_provider,
)

_CONTEXT = {
    "goal_statement": "deliver a reporting slice a reviewer can read",
    "acceptance_criteria": ["a reviewer can read one report", "the report refreshes nightly"],
    "goal_constraints": ["non-production only"],
    "selected_option": "the boring way",
}


def _request(**overrides) -> ReasoningRequest:
    return ReasoningRequest(verb="decompose_plan", context={**_CONTEXT, **overrides})


def test_the_verb_is_registered_alongside_the_original_three():
    assert REASONING_VERBS == ("propose", "critique", "summarize_decision", "decompose_plan")
    assert ARTIFACT_TYPE_FOR_VERB["decompose_plan"] is PlanDraftArtifact
    # The three that existed before are untouched.
    assert ARTIFACT_TYPE_FOR_VERB["propose"].__name__ == "ProposalArtifact"
    assert ARTIFACT_TYPE_FOR_VERB["critique"].__name__ == "CritiqueArtifact"
    assert ARTIFACT_TYPE_FOR_VERB["summarize_decision"].__name__ == "DecisionSummaryArtifact"


def test_the_artifact_reuses_plan_content_rather_than_mirroring_it():
    artifact = MockReasoningProvider().decompose_plan(_request())
    assert isinstance(artifact.plan, PlanContent)
    assert artifact.summary and artifact.rationale_summary
    # Closed schema, like every other reasoning artifact.
    with pytest.raises(Exception):
        PlanDraftArtifact(
            summary="s", rationale_summary="r", plan=artifact.plan, extra_field="nope"
        )
    # And a plan that is not a plan is refused by the model that already knows what one is.
    with pytest.raises(Exception):
        PlanDraftArtifact(summary="s", rationale_summary="r", plan="just do it")


def test_the_plan_is_valid_by_the_canonical_rules_not_by_luck():
    plan = MockReasoningProvider().decompose_plan(_request()).plan
    keys = [step.step_key for step in plan.steps]
    assert len(keys) == len(set(keys))
    for step in plan.steps:
        assert set(step.depends_on) <= set(keys)
        assert step.step_key not in step.depends_on
    # Re-parsing the serialized form through PlanContent is what the decision path does.
    assert PlanContent(**plan.model_dump(mode="json")) == plan


def test_the_same_goal_always_produces_the_same_plan():
    """Determinism is load-bearing: it is what makes an unchanged plan detectable at all."""
    first = MockReasoningProvider().decompose_plan(_request()).plan.model_dump(mode="json")
    second = MockReasoningProvider().decompose_plan(_request()).plan.model_dump(mode="json")
    assert first == second

    # Only the Goal shapes the plan. The convergence prose around it does not.
    unrelated = MockReasoningProvider().decompose_plan(
        _request(selected_option="something else entirely", proposal_summaries=["a", "b"])
    )
    assert unrelated.plan.model_dump(mode="json") == first

    # A different Goal does produce a different plan.
    other = MockReasoningProvider().decompose_plan(
        _request(goal_statement="deliver something else", acceptance_criteria=["a different one"])
    )
    assert other.plan.model_dump(mode="json") != first


def test_the_plan_decomposes_the_acceptance_criteria():
    plan = MockReasoningProvider().decompose_plan(_request()).plan
    assert len(plan.steps) == len(_CONTEXT["acceptance_criteria"])
    assert plan.steps[0].title == _CONTEXT["acceptance_criteria"][0]
    assert plan.steps[1].depends_on == (plan.steps[0].step_key,)
    assert plan.steps[0].required_capabilities
    assert list(plan.constraints) == _CONTEXT["goal_constraints"]

    # A goal with no criteria still yields one usable step rather than an empty plan.
    bare = MockReasoningProvider().decompose_plan(_request(acceptance_criteria=[])).plan
    assert len(bare.steps) == 1


def test_the_artifact_carries_no_hidden_reasoning_and_says_it_is_mock():
    artifact = MockReasoningProvider().decompose_plan(_request())
    payload = artifact.as_safe_dict()  # runs the same content-safety screen a TeamMessage does
    assert "[mock]" in payload["summary"]
    assert "no live model was consulted" in payload["rationale_summary"]
    for forbidden in ("chain_of_thought", "scratchpad", "raw_prompt", "completion", "token_trace"):
        assert forbidden not in str(payload)


def test_a_disabled_provider_refuses_the_new_verb_exactly_as_it_refuses_the_others():
    provider = DisabledReasoningProvider()
    with pytest.raises(ReasoningProviderError):
        provider.decompose_plan(_request())
    # And no name other than 'mock' resolves to something that can plan.
    assert isinstance(get_reasoning_provider("external_anthropic"), DisabledReasoningProvider)
    with pytest.raises(ReasoningProviderError):
        get_reasoning_provider("external_anthropic").decompose_plan(_request())


def test_the_mock_provider_reaches_no_network():
    import inspect

    import shared.sdk.agent_reasoning.mock_provider as module

    source = inspect.getsource(module)
    for forbidden in ("httpx", "requests", "urllib", "socket", "aiohttp", "openai", "anthropic"):
        assert forbidden not in source, forbidden
    assert get_reasoning_provider("mock").mode == "mock"
