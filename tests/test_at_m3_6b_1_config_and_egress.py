"""Step AT-M3.6B.1 -- configuration authority, the live gate, and the outbound egress boundary.

These are the controls that decide whether a call happens at all and what leaves the machine if it
does. None of them needs a database or a network, and all of them are the kind of thing that is
easy to assert and expensive to get wrong.
"""

from __future__ import annotations

import json

import pytest

from shared.sdk.agent_planning.models import PlanContent, PlanStep
from shared.sdk.agent_reasoning.egress import (
    ALLOWED_CONTEXT_KEYS,
    MAX_CONTEXT_BYTES,
    EgressViolationError,
    approved_outbound_context,
    context_size,
    project_context,
)
from shared.sdk.agent_reasoning.live_config import (
    ATTEMPT_TIMEOUT_SECONDS,
    AUTHORIZED_MODELS,
    CONNECT_TIMEOUT_SECONDS,
    ENV_LIVE_NETWORK_ENABLED,
    LEASE_TTL_SECONDS_REFERENCE,
    LIVE_PROVIDER_NAME,
    MAX_COST_PER_CALL_USD,
    MAX_COST_PER_INVOCATION_USD,
    MAX_OUTPUT_TOKENS_BY_VERB,
    LiveReasoningConfig,
    LiveReasoningConfigError,
    generation_profile,
)
from shared.sdk.agent_reasoning.models import REASONING_VERBS
from shared.sdk.agent_reasoning.provider import DisabledReasoningProvider, get_reasoning_provider
from shared.sdk.agent_reasoning.store import DEFAULT_LEASE_TTL_SECONDS, DEFAULT_MAX_ATTEMPTS

# --- the gate ------------------------------------------------------------------------------------


class TestLiveNetworkGate:
    def test_default_posture_is_mock_and_closed(self) -> None:
        """An unconfigured runtime resolves the mock and is not permitted to call anybody."""
        config = LiveReasoningConfig.resolve({})
        assert config.provider_name == "mock"
        assert config.live_network_enabled is False

    def test_gate_defaults_closed_even_when_the_provider_is_configured(self) -> None:
        config = LiveReasoningConfig.resolve({"REASONING_PROVIDER": "anthropic"})
        assert config.provider_name == LIVE_PROVIDER_NAME
        assert config.live_network_enabled is False
        with pytest.raises(LiveReasoningConfigError, match="network access is disabled"):
            config.assert_callable()

    def test_only_the_literal_true_opens_the_gate(self) -> None:
        for raw in ("false", "0", "yes", "TRUE ", "", "1", "on"):
            config = LiveReasoningConfig.resolve(
                {"REASONING_PROVIDER": "anthropic", ENV_LIVE_NETWORK_ENABLED: raw}
            )
            if raw.strip().lower() == "true":
                assert config.live_network_enabled is True, raw
            else:
                assert config.live_network_enabled is False, raw

    def test_the_gate_is_checked_before_the_model(self) -> None:
        """A closed gate refuses without the allowlist ever being consulted.

        Ordering, not cosmetics: the refusal a disabled runtime gives must not depend on the rest of
        the configuration being valid, or a deployment could be told its model is wrong when the
        real answer is that it may not call anybody.
        """
        config = LiveReasoningConfig(
            provider_name="anthropic", model_name="some-other-model", live_network_enabled=False
        )
        with pytest.raises(LiveReasoningConfigError) as caught:
            config.assert_callable()
        assert "network access is disabled" in str(caught.value)
        assert "allowlist" not in str(caught.value)


class TestModelAllowlist:
    def test_exactly_one_model_is_authorized(self) -> None:
        assert AUTHORIZED_MODELS == frozenset({"claude-sonnet-5"})

    def test_an_unlisted_model_fails_closed(self) -> None:
        config = LiveReasoningConfig(
            provider_name="anthropic",
            model_name="claude-3-opus",
            live_network_enabled=True,
        )
        assert config.model_is_authorized is False
        with pytest.raises(LiveReasoningConfigError, match="allowlist"):
            config.assert_callable()

    def test_a_different_provider_fails_closed(self) -> None:
        config = LiveReasoningConfig(
            provider_name="openai", model_name="claude-sonnet-5", live_network_enabled=True
        )
        with pytest.raises(LiveReasoningConfigError, match="not the authorized provider"):
            config.assert_callable()


class TestProviderIsNotReachableByName:
    """The adversarial property: a request field must not be able to route to a paid model."""

    @pytest.mark.parametrize(
        "requested",
        ["anthropic", "ANTHROPIC", " anthropic ", "claude", "external_anthropic", "live"],
    )
    def test_a_caller_supplied_name_never_resolves_the_live_adapter(
        self, requested: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("REASONING_PROVIDER", raising=False)
        provider = get_reasoning_provider(requested)
        assert isinstance(provider, DisabledReasoningProvider)
        assert provider.mode == "disabled"

    def test_a_caller_cannot_downgrade_a_live_runtime_to_mock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other direction, and the one that is easy to forget.

        If a request could select ``mock`` on a live deployment, a caller could have mock-authored
        content recorded indistinguishably from a real model's -- which is precisely the
        substitution AT-D14 section 4's first safety invariant forbids.
        """
        monkeypatch.setenv("REASONING_PROVIDER", "anthropic")
        provider = get_reasoning_provider("mock")
        assert provider.name == LIVE_PROVIDER_NAME
        assert provider.mode == "live"

    def test_configured_mock_still_resolves_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REASONING_PROVIDER", "mock")
        assert get_reasoning_provider().mode == "mock"


# --- generation ------------------------------------------------------------------------------------


class TestGenerationProfiles:
    def test_every_reasoning_verb_has_a_fixed_output_ceiling(self) -> None:
        assert set(MAX_OUTPUT_TOKENS_BY_VERB) == set(REASONING_VERBS)

    def test_the_approved_ceilings(self) -> None:
        assert MAX_OUTPUT_TOKENS_BY_VERB == {
            "propose": 1500,
            "critique": 1500,
            "summarize_decision": 1500,
            "decompose_plan": 4000,
        }

    def test_profiles_are_fixed_and_carry_no_caller_input(self) -> None:
        for verb in REASONING_VERBS:
            profile = generation_profile(verb)
            assert profile.verb == verb
            assert profile.max_output_tokens == MAX_OUTPUT_TOKENS_BY_VERB[verb]
            assert profile.temperature == 0.2

    def test_an_unknown_verb_has_no_profile(self) -> None:
        with pytest.raises(LiveReasoningConfigError):
            generation_profile("execute_code")


class TestTimeoutsAgainstTheLease:
    def test_connect_is_shorter_than_the_attempt_bound(self) -> None:
        assert CONNECT_TIMEOUT_SECONDS < ATTEMPT_TIMEOUT_SECONDS

    def test_the_attempt_fits_inside_the_lease_with_margin(self) -> None:
        """The load-bearing ordering.

        An attempt that outlives its lease gets taken over, and a takeover turns one logical
        reasoning call into two billable provider calls. The margin is what parsing, validation and
        the terminal commit run in.
        """
        assert LEASE_TTL_SECONDS_REFERENCE == float(DEFAULT_LEASE_TTL_SECONDS)
        worst_case = CONNECT_TIMEOUT_SECONDS + ATTEMPT_TIMEOUT_SECONDS
        assert worst_case < LEASE_TTL_SECONDS_REFERENCE
        assert LEASE_TTL_SECONDS_REFERENCE - worst_case >= 30.0

    def test_the_lease_was_not_raised_to_accommodate_the_provider(self) -> None:
        assert DEFAULT_LEASE_TTL_SECONDS == 120


class TestCostCeilings:
    def test_the_invocation_ceiling_is_the_call_ceiling_times_the_attempt_budget(self) -> None:
        """One number, not two. Bounding the per-call estimate bounds the envelope by construction."""
        assert MAX_COST_PER_CALL_USD == 0.50
        assert DEFAULT_MAX_ATTEMPTS == 3
        assert MAX_COST_PER_INVOCATION_USD == pytest.approx(
            MAX_COST_PER_CALL_USD * DEFAULT_MAX_ATTEMPTS
        )


# --- egress ---------------------------------------------------------------------------------------


def _deliberation_context() -> dict[str, object]:
    return {
        "topic": "how should we sequence the migration",
        "round": 1,
        "goal_statement": "ship the read surface",
        "goal_acceptance_criteria": ["a", "b"],
        "goal_constraints": ["no production"],
        "speaker_role": "architect",
        "speaker_capabilities": ["design"],
        "recent_messages": [{"message_type": "proposal", "summary": "start with the schema"}],
        "plan_revision_number": 3,
        "plan_objective": "deliver the goal",
        "plan_step_titles": ["schema", "api"],
        "proposal_summary": "start with the schema",
    }


class TestEgressProjection:
    def test_every_verb_has_an_approved_shape(self) -> None:
        assert set(ALLOWED_CONTEXT_KEYS) == set(REASONING_VERBS)

    def test_the_real_deliberation_context_projects_cleanly(self) -> None:
        """The allowlist is derived from what M3.3 actually builds, so M3.3's own context must pass.

        This is the test that fails if an upstream service adds a field without review -- which is
        the entire reason the projector rejects rather than silently drops.
        """
        projection = approved_outbound_context("propose", _deliberation_context())
        assert projection == _deliberation_context()

    def test_the_real_planner_context_projects_cleanly(self) -> None:
        context = {
            "goal_statement": "ship it",
            "acceptance_criteria": ["a"],
            "goal_constraints": [],
            "selected_option": "option A",
            "options_considered": ["option A", "option B"],
            "dissent_summary": None,
            "proposal_summaries": ["p1"],
            "challenge_summaries": ["c1"],
            "current_plan": {"objective": "o", "steps": []},
        }
        assert approved_outbound_context("decompose_plan", context) == context

    def test_an_unapproved_field_fails_closed(self) -> None:
        context = {**_deliberation_context(), "other_project_internal_note": "leak me"}
        with pytest.raises(EgressViolationError) as caught:
            project_context("propose", context)
        assert "other_project_internal_note" in str(caught.value)

    def test_the_rejection_never_echoes_the_unapproved_VALUE(self) -> None:
        """An unapproved field is exactly the field whose content must not reach a log."""
        context = {**_deliberation_context(), "internal_note": "SENSITIVE-PAYLOAD-VALUE"}
        with pytest.raises(EgressViolationError) as caught:
            project_context("propose", context)
        assert "SENSITIVE-PAYLOAD-VALUE" not in str(caught.value)

    def test_a_planner_field_is_not_authorized_for_a_discussion_turn(self) -> None:
        """The allowlist is per verb, not one union. A propose turn has no business sending a plan."""
        with pytest.raises(EgressViolationError, match="current_plan"):
            project_context("propose", {"current_plan": {"objective": "o", "steps": []}})

    def test_an_unknown_verb_has_no_approved_shape(self) -> None:
        with pytest.raises(EgressViolationError, match="no approved outbound egress shape"):
            project_context("exfiltrate", {})

    def test_a_forbidden_key_is_rejected_at_the_boundary(self) -> None:
        """The same screen a TeamMessage passes, applied to the payload that is about to leave."""
        with pytest.raises(ValueError, match="forbidden key"):
            project_context("propose", {"recent_messages": [{"chain_of_thought": "..."}]})

    def test_generation_parameters_cannot_be_injected_through_context(self) -> None:
        for injected in ("temperature", "max_tokens", "top_p", "model", "system"):
            with pytest.raises(EgressViolationError, match=injected):
                project_context("propose", {injected: 1})


class TestOutboundSizeBound:
    def test_the_bound_is_32_kib(self) -> None:
        assert MAX_CONTEXT_BYTES == 32 * 1024

    def test_an_oversized_context_fails_closed(self) -> None:
        context = {**_deliberation_context(), "goal_statement": "x" * (MAX_CONTEXT_BYTES + 1)}
        with pytest.raises(EgressViolationError, match="exceeds the authorized maximum"):
            approved_outbound_context("propose", context)

    def test_a_maximal_bounded_plan_still_fits(self) -> None:
        """The plan bound and the context bound have to agree, or the planner cannot run at all.

        A 40-step plan with a full dependency fan-in is the largest ``current_plan`` the schema now
        admits, and it has to survive the outbound projection -- otherwise the two limits would
        contradict each other and every real decompose_plan would be refused.
        """
        steps = [PlanStep(step_key=f"step-{i}", title=f"step {i} title") for i in range(40)]
        plan = PlanContent(objective="deliver", steps=tuple(steps))
        context = {
            "goal_statement": "ship it",
            "acceptance_criteria": ["a"],
            "goal_constraints": [],
            "selected_option": "A",
            "options_considered": ["A", "B"],
            "dissent_summary": None,
            "proposal_summaries": [],
            "challenge_summaries": [],
            "current_plan": plan.model_dump(mode="json"),
        }
        assert (
            context_size(approved_outbound_context("decompose_plan", context)) < MAX_CONTEXT_BYTES
        )

    def test_the_measurement_is_deterministic(self) -> None:
        context = _deliberation_context()
        first = approved_outbound_context("propose", context)
        second = approved_outbound_context("propose", dict(reversed(list(context.items()))))
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
        assert context_size(first) == context_size(second)
