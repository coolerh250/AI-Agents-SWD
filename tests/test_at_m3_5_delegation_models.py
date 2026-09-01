"""Step AT-M3.5 -- the pure delegation logic: graph validation, capability routing, envelope.

No database and no transport here. What these assert is that the DECISIONS are functions of the
plan and the team -- so that changing the team changes who gets the work, and changing nothing
changes nothing. The concurrency, idempotency and lineage guarantees are database facts and are
asserted against a real PostgreSQL in ``test_at_m3_5_delegation_store.py``.

The load-bearing negative here is the successor test: AT-M1 verified that today's chain
``intake -> requirement -> development -> qa -> devops`` is a compile-time constant, and AT-D04-R4
requires ownership to come from capability instead. A test that only showed "an agent was chosen"
would pass just as happily against a hard-coded successor table, so what is asserted is that the
SAME plan step routes somewhere else when the team changes.
"""

from __future__ import annotations

import pytest

from shared.sdk.agent_planning.models import PlanStepDraftError, parse_plan
from shared.sdk.agent_team.capabilities import (
    GENERATE_CODE,
    PLAN_DEPLOYMENT,
    VERIFY_QUALITY,
)
from shared.sdk.agent_team.router import RoutingCandidate
from shared.sdk.plan_delegation.models import (
    UNAVAILABLE_NO_ELIGIBLE_AGENT,
    UNAVAILABLE_REQUIRES_HUMAN_APPROVAL,
    UNIT_ASSIGNED,
    UNIT_BLOCKED,
    UNIT_CANCELLED,
    UNIT_COMPLETED,
    UNIT_DISPATCHED,
    UNIT_FAILED,
    UNIT_READY,
    PlanGraphInvalidError,
    build_dispatch_envelope,
    plan_dependency_edges,
    resolve_step_assignment,
    root_step_keys,
    unavailable_reason_for,
    validate_plan_graph,
    work_item_status_for,
)

PROJECT = "11111111-1111-4111-8111-111111111111"


def _plan(steps: list[dict], objective: str = "ship the thing") -> dict:
    return {"objective": objective, "steps": steps}


def _chain_plan() -> dict:
    return _plan(
        [
            {
                "step_key": "design",
                "title": "Design the API",
                "required_capabilities": ["review_design"],
            },
            {
                "step_key": "build",
                "title": "Build the API",
                "required_capabilities": [GENERATE_CODE],
                "depends_on": ["design"],
            },
            {
                "step_key": "verify",
                "title": "Verify the API",
                "required_capabilities": [VERIFY_QUALITY],
                "depends_on": ["build"],
            },
        ]
    )


def _candidate(
    agent_key: str,
    role: str,
    capabilities: tuple[str, ...],
    *,
    stream: str | None = None,
    membership_state: str = "active",
    profile_status: str = "active",
) -> RoutingCandidate:
    return RoutingCandidate(
        principal_id=f"00000000-0000-4000-8000-{abs(hash(agent_key)) % 10**12:012d}",
        agent_key=agent_key,
        role=role,
        capabilities=frozenset(capabilities),
        transport_stream=stream or f"stream.{role}",
        membership_state=membership_state,
        profile_status=profile_status,
    )


# --- graph validation -----------------------------------------------------------------------------


class TestPlanGraphValidation:
    def test_a_chain_plan_is_executable_and_has_exactly_one_root(self):
        plan = parse_plan(_chain_plan())
        validate_plan_graph(plan)
        assert root_step_keys(plan) == ("design",)
        assert plan_dependency_edges(plan) == (("build", "design"), ("verify", "build"))

    def test_a_fan_in_plan_has_two_roots_and_both_are_ready_immediately(self):
        plan = parse_plan(
            _plan(
                [
                    {"step_key": "a", "title": "A"},
                    {"step_key": "b", "title": "B"},
                    {"step_key": "c", "title": "C", "depends_on": ["a", "b"]},
                ]
            )
        )
        validate_plan_graph(plan)
        assert root_step_keys(plan) == ("a", "b")

    def test_a_cycle_is_rejected_although_PlanContent_accepts_it(self):
        """The genuinely new check. Every step exists and none depends on itself, so
        ``PlanContent`` is satisfied -- and nothing in the graph could ever become ready."""
        payload = _plan(
            [
                {"step_key": "a", "title": "A", "depends_on": ["b"]},
                {"step_key": "b", "title": "B", "depends_on": ["a"]},
            ]
        )
        plan = parse_plan(payload)  # PlanContent has no objection
        with pytest.raises(PlanGraphInvalidError) as exc:
            validate_plan_graph(plan)
        assert any(error["type"] == "cycle" for error in exc.value.errors)

    def test_a_three_step_cycle_is_rejected(self):
        plan = parse_plan(
            _plan(
                [
                    {"step_key": "a", "title": "A", "depends_on": ["c"]},
                    {"step_key": "b", "title": "B", "depends_on": ["a"]},
                    {"step_key": "c", "title": "C", "depends_on": ["b"]},
                ]
            )
        )
        with pytest.raises(PlanGraphInvalidError):
            validate_plan_graph(plan)

    def test_a_plan_with_no_steps_materializes_no_work_and_is_refused(self):
        plan = parse_plan(_plan([]))
        with pytest.raises(PlanGraphInvalidError, match="no steps"):
            validate_plan_graph(plan)

    def test_an_isolated_step_beside_a_chain_is_legitimate(self):
        """The shared validator warns about it; a standalone step is a real plan shape, and a
        warning is not a refusal."""
        plan = parse_plan(
            _plan(
                [
                    {"step_key": "a", "title": "A"},
                    {"step_key": "b", "title": "B", "depends_on": ["a"]},
                    {"step_key": "loner", "title": "Independent"},
                ]
            )
        )
        validate_plan_graph(plan)
        assert set(root_step_keys(plan)) == {"a", "loner"}

    def test_a_dependency_on_a_step_that_does_not_exist_is_refused_by_PlanContent(self):
        with pytest.raises(PlanStepDraftError, match="unknown step"):
            parse_plan(_plan([{"step_key": "a", "title": "A", "depends_on": ["ghost"]}]))

    def test_a_duplicate_step_key_is_refused_by_PlanContent(self):
        with pytest.raises(PlanStepDraftError, match="duplicate"):
            parse_plan(
                _plan([{"step_key": "a", "title": "A"}, {"step_key": "a", "title": "Also A"}])
            )


# --- capability routing ----------------------------------------------------------------------------


class TestCapabilityAssignment:
    def test_the_step_goes_to_the_agent_that_declares_its_capability(self):
        decision = resolve_step_assignment(
            required_capabilities=(VERIFY_QUALITY,),
            candidates=[
                _candidate("development-agent", "development", (GENERATE_CODE,)),
                _candidate("qa-agent", "qa", (VERIFY_QUALITY,)),
            ],
            project_id=PROJECT,
        )
        assert decision.outcome == "selected"
        assert decision.selected_agent_key == "qa-agent"
        assert decision.selected_stream == "stream.qa"

    def test_the_same_step_routes_elsewhere_when_the_team_changes(self):
        """Not a fixed successor chain. AT-D04-R4: ownership is decided by capability over the
        CURRENT team, so removing the specialist moves the work rather than failing to a
        compile-time next node."""
        step_capabilities = (VERIFY_QUALITY,)
        specialist = _candidate("qa-agent", "qa", (VERIFY_QUALITY,))
        generalist = _candidate(
            "utility-agent", "utility", (GENERATE_CODE, VERIFY_QUALITY, PLAN_DEPLOYMENT)
        )

        with_specialist = resolve_step_assignment(
            required_capabilities=step_capabilities,
            candidates=[specialist, generalist],
            project_id=PROJECT,
        )
        without_specialist = resolve_step_assignment(
            required_capabilities=step_capabilities,
            candidates=[generalist],
            project_id=PROJECT,
        )
        assert with_specialist.selected_agent_key == "qa-agent"
        assert without_specialist.selected_agent_key == "utility-agent"

    def test_selection_is_deterministic_across_repeated_calls_and_input_order(self):
        peers = [
            _candidate("alpha-agent", "development", (GENERATE_CODE,)),
            _candidate("beta-agent", "development", (GENERATE_CODE,)),
        ]
        forward = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE,), candidates=peers, project_id=PROJECT
        )
        reversed_order = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE,),
            candidates=list(reversed(peers)),
            project_id=PROJECT,
        )
        assert forward.selected_agent_key == reversed_order.selected_agent_key == "alpha-agent"

    def test_a_step_requiring_two_capabilities_needs_ONE_agent_covering_BOTH(self):
        """Two half-qualified agents are not a qualified agent. The AT-M2 router answers about one
        capability at a time; the conjunction is what this slice adds."""
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE, VERIFY_QUALITY),
            candidates=[
                _candidate("development-agent", "development", (GENERATE_CODE,)),
                _candidate("qa-agent", "qa", (VERIFY_QUALITY,)),
            ],
            project_id=PROJECT,
        )
        assert decision.outcome == "no_eligible_agent"
        assert unavailable_reason_for(decision) == UNAVAILABLE_NO_ELIGIBLE_AGENT
        assert "covers all of" in decision.reason

    def test_a_step_requiring_two_capabilities_selects_the_agent_that_covers_both(self):
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE, VERIFY_QUALITY),
            candidates=[
                _candidate("development-agent", "development", (GENERATE_CODE,)),
                _candidate("fullstack-agent", "development", (GENERATE_CODE, VERIFY_QUALITY)),
            ],
            project_id=PROJECT,
        )
        assert decision.outcome == "selected"
        assert decision.selected_agent_key == "fullstack-agent"
        assert "covers all of" in decision.reason

    def test_every_candidate_appears_in_the_evidence_with_what_it_was_missing(self):
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE, VERIFY_QUALITY),
            candidates=[
                _candidate("development-agent", "development", (GENERATE_CODE,)),
                _candidate("fullstack-agent", "development", (GENERATE_CODE, VERIFY_QUALITY)),
            ],
            project_id=PROJECT,
        )
        evidence = {c["agent_key"]: c for c in decision.candidates_considered}
        assert evidence["development-agent"]["eligible"] is False
        assert evidence["development-agent"]["rejected_because"] == f"missing:{VERIFY_QUALITY}"
        assert evidence["fullstack-agent"]["eligible"] is True

    def test_an_empty_team_fails_closed_rather_than_choosing_anyone(self):
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE,), candidates=[], project_id=PROJECT
        )
        assert decision.outcome == "no_eligible_agent"
        assert decision.selected_principal_id is None

    def test_an_inactive_member_is_not_eligible_however_capable(self):
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE,),
            candidates=[
                _candidate(
                    "development-agent", "development", (GENERATE_CODE,), membership_state="paused"
                )
            ],
            project_id=PROJECT,
        )
        assert decision.outcome == "no_eligible_agent"

    def test_a_disabled_profile_is_not_eligible_however_active_the_membership(self):
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE,),
            candidates=[
                _candidate(
                    "development-agent", "development", (GENERATE_CODE,), profile_status="disabled"
                )
            ],
            project_id=PROJECT,
        )
        assert decision.outcome == "no_eligible_agent"

    def test_a_production_effect_capability_is_referred_to_the_human_boundary_not_routed(self):
        decision = resolve_step_assignment(
            required_capabilities=("deploy_production",),
            candidates=[_candidate("devops-agent", "devops", ("deploy_production",))],
            project_id=PROJECT,
        )
        assert decision.outcome == "requires_human_approval"
        assert decision.selected_principal_id is None
        assert unavailable_reason_for(decision) == UNAVAILABLE_REQUIRES_HUMAN_APPROVAL

    def test_a_production_effect_capability_hidden_among_safe_ones_still_refers(self):
        """The router checks the capability it was asked about. A step requiring a safe capability
        AND a production-effect one must be referred, not routed on the safe half."""
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE, "deploy_production"),
            candidates=[
                _candidate("over-powered-agent", "devops", (GENERATE_CODE, "deploy_production"))
            ],
            project_id=PROJECT,
        )
        assert decision.outcome == "requires_human_approval"
        assert decision.selected_principal_id is None

    def test_a_step_declaring_no_capability_selects_nobody(self):
        decision = resolve_step_assignment(
            required_capabilities=(),
            candidates=[_candidate("development-agent", "development", (GENERATE_CODE,))],
            project_id=PROJECT,
        )
        assert decision.outcome == "no_eligible_agent"
        assert "no required capability" in decision.reason


class TestOwnershipIntent:
    def test_plan_intent_prefers_an_eligible_matching_role(self):
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE,),
            candidates=[
                _candidate("alpha-agent", "development", (GENERATE_CODE,)),
                _candidate("beta-agent", "backend", (GENERATE_CODE,)),
            ],
            project_id=PROJECT,
            intended_owner_role="backend",
        )
        assert decision.selected_agent_key == "beta-agent"

    def test_plan_intent_cannot_conjure_a_principal_that_is_not_on_the_team(self):
        """The plan may say what it WANTS. It may not invent who exists: an intent matching nobody
        eligible is ignored, and the capability answer stands."""
        decision = resolve_step_assignment(
            required_capabilities=(GENERATE_CODE,),
            candidates=[_candidate("alpha-agent", "development", (GENERATE_CODE,))],
            project_id=PROJECT,
            intended_owner_role="a-role-nobody-holds",
        )
        assert decision.outcome == "selected"
        assert decision.selected_agent_key == "alpha-agent"

    def test_plan_intent_cannot_override_capability(self):
        """A role hint pointing at someone who cannot do the work does not get them the work."""
        decision = resolve_step_assignment(
            required_capabilities=(VERIFY_QUALITY,),
            candidates=[
                _candidate("development-agent", "development", (GENERATE_CODE,)),
                _candidate("qa-agent", "qa", (VERIFY_QUALITY,)),
            ],
            project_id=PROJECT,
            intended_owner_role="development",
        )
        assert decision.selected_agent_key == "qa-agent"


# --- dispatch envelope -----------------------------------------------------------------------------


class TestDispatchEnvelope:
    @staticmethod
    def _envelope():
        plan = parse_plan(_chain_plan())
        step = next(s for s in plan.steps if s.step_key == "build")
        return build_dispatch_envelope(
            project_id=PROJECT,
            goal_id="22222222-2222-4222-8222-222222222222",
            primary_work_item_id="33333333-3333-4333-8333-333333333333",
            work_item_id="44444444-4444-4444-8444-444444444444",
            execution_unit_id="55555555-5555-4555-8555-555555555555",
            plan_revision_id="66666666-6666-4666-8666-666666666666",
            step=step,
            assigned_principal_id="77777777-7777-4777-8777-777777777777",
            assigned_role="development",
            correlation_id="88888888-8888-4888-8888-888888888888",
        )

    def test_it_carries_the_whole_lineage_so_the_dispatch_is_reconstructable(self):
        envelope = self._envelope()
        for key in (
            "project_id",
            "goal_id",
            "primary_work_item_id",
            "work_item_id",
            "execution_unit_id",
            "plan_revision_id",
            "step_key",
            "assigned_principal_id",
            "correlation_id",
        ):
            assert envelope[key], key

    def test_it_carries_only_this_step_never_the_whole_plan(self):
        envelope = self._envelope()
        assert envelope["step_key"] == "build"
        assert envelope["depends_on"] == ["design"]
        # The plan's objective, its other steps and its acceptance criteria are NOT the assigned
        # principal's business: a bounded contract, not unrestricted internal state.
        assert "objective" not in envelope
        assert "steps" not in envelope
        assert "acceptance_criteria" not in envelope
        assert "plan" not in envelope

    def test_every_external_effect_is_declared_false(self):
        envelope = self._envelope()
        for flag in (
            "production_action",
            "production_effect",
            "github_write",
            "argocd_sync",
            "external_notification_send",
            "code_execution",
        ):
            assert envelope[flag] is False, flag

    def test_it_carries_no_reasoning_no_transcript_and_no_secret(self):
        envelope = self._envelope()
        for forbidden in (
            "chain_of_thought",
            "raw_prompt",
            "system_prompt",
            "scratchpad",
            "reasoning",
            "discussion_id",
            "messages",
            "api_key",
            "token",
        ):
            assert forbidden not in envelope, forbidden

    def test_a_forbidden_key_smuggled_into_a_step_is_refused_not_scrubbed(self):
        """``expected_outputs`` is a list of strings, so the screen is exercised through the one
        route a caller could reach it by -- the envelope as a whole."""
        plan = parse_plan(
            _plan([{"step_key": "s", "title": "T", "expected_outputs": ["a report"]}])
        )
        step = plan.steps[0]
        envelope = build_dispatch_envelope(
            project_id=PROJECT,
            goal_id=PROJECT,
            primary_work_item_id=PROJECT,
            work_item_id=PROJECT,
            execution_unit_id=PROJECT,
            plan_revision_id=PROJECT,
            step=step,
            assigned_principal_id=PROJECT,
            assigned_role=None,
            correlation_id=PROJECT,
        )
        envelope["api_key_for_downstream"] = "anything"
        from shared.sdk.agent_team.models import assert_content_is_safe

        with pytest.raises(ValueError, match="forbidden key"):
            assert_content_is_safe(envelope, field="dispatch_envelope")


class TestWorkItemMirroring:
    def test_every_unit_state_maps_to_a_real_work_item_status(self):
        allowed = {
            "pending",
            "ready",
            "in_progress",
            "blocked",
            "review",
            "completed",
            "failed",
            "cancelled",
        }
        for state in (
            UNIT_BLOCKED,
            UNIT_READY,
            UNIT_ASSIGNED,
            UNIT_DISPATCHED,
            UNIT_COMPLETED,
            UNIT_FAILED,
            UNIT_CANCELLED,
        ):
            assert work_item_status_for(state) in allowed

    def test_a_dispatched_step_reads_as_in_progress_on_its_work_item(self):
        assert work_item_status_for(UNIT_DISPATCHED) == "in_progress"
