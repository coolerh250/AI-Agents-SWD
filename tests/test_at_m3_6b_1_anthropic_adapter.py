"""Step AT-M3.6B.1 -- the Anthropic adapter, driven entirely through an in-process transport.

ZERO real external calls. Every test here builds a real ``httpx`` request, a real client and the
real fixed URL, and replaces only the socket -- so the headers, the timeout configuration, the retry
posture and the parsing are the production ones. A fake that stubbed the adapter's own ``_call``
would prove none of that, and those are exactly the things a live adapter gets wrong.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from shared.sdk.agent_reasoning import anthropic_provider as adapter_module
from shared.sdk.agent_reasoning.anthropic_provider import AnthropicReasoningProvider
from shared.sdk.agent_reasoning.live_config import (
    ANTHROPIC_API_BASE,
    ANTHROPIC_MESSAGES_PATH,
    ANTHROPIC_SECRET_NAME,
    MAX_COST_PER_CALL_USD,
    MAX_OUTPUT_TOKENS_BY_VERB,
)
from shared.sdk.agent_reasoning.models import (
    MAX_ARTIFACT_BYTES,
    PlanDraftArtifact,
    ProposalArtifact,
    ReasoningRequest,
)
from shared.sdk.agent_reasoning.provider import LiveProviderError, ProviderResult
from tests.at_m3_6b_1_fakes import (
    FAKE_API_KEY,
    ExplodingSecretProvider,
    FakeBudgetEvaluator,
    FakePolicy,
    FakeSecretProvider,
    SlowTransport,
    anthropic_body,
    blocked_evaluator,
    live_config,
    responding,
    returning_artifact,
    returning_text,
    valid_artifact_json,
)

pytestmark = pytest.mark.asyncio


def _context() -> dict[str, object]:
    return {
        "topic": "sequence the work",
        "round": 1,
        "goal_statement": "ship the adapter",
        "goal_acceptance_criteria": ["bounded"],
        "goal_constraints": [],
        "speaker_role": "architect",
        "speaker_capabilities": ["design"],
        "recent_messages": [{"message_type": "proposal", "summary": "start small"}],
        "proposal_summary": "start small",
    }


def _request(verb: str = "propose", **overrides: object) -> ReasoningRequest:
    payload: dict[str, object] = {"verb": verb, "context": _context()}
    payload.update(overrides)
    return ReasoningRequest(**payload)  # type: ignore[arg-type]


def _provider(
    *,
    transport: object | None = None,
    enabled: bool = True,
    model: str | None = None,
    secrets: object | None = None,
    evaluator: object | None = None,
) -> AnthropicReasoningProvider:
    return AnthropicReasoningProvider(
        config=live_config(enabled=enabled, model=model),
        secret_provider=secrets if secrets is not None else FakeSecretProvider(),
        budget_evaluator=evaluator if evaluator is not None else FakeBudgetEvaluator(),
        transport=transport,
    )


# --- identity ------------------------------------------------------------------------------------


class TestIdentity:
    async def test_provider_identity_and_mode_are_separate_facts(self) -> None:
        provider = _provider()
        assert provider.name == "anthropic"
        assert provider.mode == "live"
        assert provider.model_name == "claude-sonnet-5"

    async def test_the_model_comes_from_configuration_not_the_request(self) -> None:
        """A request naming another model changes nothing about what is actually called."""
        transport = returning_artifact("propose")
        provider = _provider(transport=transport)
        await provider.propose(_request(model_name="claude-3-opus", provider_name="openai"))
        assert transport.payload()["model"] == "claude-sonnet-5"


# --- the outbound request --------------------------------------------------------------------------


class TestRequestBuilder:
    async def test_the_endpoint_is_the_fixed_runtime_owned_url(self) -> None:
        transport = returning_artifact("propose")
        await _provider(transport=transport).propose(_request())
        assert str(transport.requests[0].url) == f"{ANTHROPIC_API_BASE}{ANTHROPIC_MESSAGES_PATH}"
        assert transport.requests[0].url.scheme == "https"

    async def test_the_credential_travels_only_in_the_header(self) -> None:
        transport = returning_artifact("propose")
        await _provider(transport=transport).propose(_request())
        request = transport.requests[0]
        assert request.headers["x-api-key"] == FAKE_API_KEY
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert FAKE_API_KEY not in request.content.decode("utf-8")

    @pytest.mark.parametrize(
        "verb", ["propose", "critique", "summarize_decision", "decompose_plan"]
    )
    async def test_generation_settings_are_the_fixed_per_verb_profile(self, verb: str) -> None:
        transport = returning_artifact(verb)
        await getattr(_provider(transport=transport), verb)(
            _request(verb, context=_plan_context(verb))
        )
        payload = transport.payload()
        assert payload["max_tokens"] == MAX_OUTPUT_TOKENS_BY_VERB[verb]
        assert payload["temperature"] == 0.2
        assert payload["model"] == "claude-sonnet-5"

    async def test_the_schema_asked_for_is_the_canonical_pydantic_model(self) -> None:
        """Derived rather than restated, so what is requested and what is enforced cannot drift."""
        transport = returning_artifact("propose")
        await _provider(transport=transport).propose(_request())
        content = transport.payload()["messages"][0]["content"]
        assert json.dumps(ProposalArtifact.model_json_schema(), sort_keys=True) in content

    async def test_only_approved_context_fields_reach_the_wire(self) -> None:
        transport = returning_artifact("propose")
        provider = _provider(transport=transport)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(
                _request(context={**_context(), "other_project_internal_note": "x"})
            )
        assert caught.value.failure_category == "provider_unauthorized"
        assert transport.call_count == 0

    async def test_the_system_instruction_is_fixed_and_forbids_hidden_reasoning(self) -> None:
        transport = returning_artifact("propose")
        await _provider(transport=transport).propose(_request())
        system = transport.payload()["system"]
        assert "chain-of-thought" in system
        assert "credentials" in system


class TestTransportPosture:
    async def test_the_runtime_transport_disables_every_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The one authoritative retry layer is ReasoningService. A transport that retries under a
        three-attempt budget multiplies worst-case spend by a factor nothing accounts for."""
        captured: dict[str, object] = {}
        real = httpx.AsyncHTTPTransport

        class _Capturing(real):  # type: ignore[misc,valid-type]
            def __init__(self, *args: object, **kwargs: object) -> None:
                captured.update(kwargs)
                super().__init__(*args, **kwargs)

            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                # Refuse at the transport rather than dialling. The claim under test is what the
                # adapter CONFIGURES, and opening a socket to find that out would itself be the
                # external call this slice authorizes zero of.
                raise httpx.ConnectError("refused by test", request=request)

        monkeypatch.setattr(httpx, "AsyncHTTPTransport", _Capturing)
        provider = _provider(transport=None)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "provider_unavailable"
        assert captured.get("retries") == 0

    async def test_timeouts_are_configured_from_the_authorized_bounds(self) -> None:
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["timeout"] = request.extensions.get("timeout")
            return httpx.Response(200, json=anthropic_body(valid_artifact_json("propose")))

        transport = httpx.MockTransport(handler)
        await _provider(transport=transport).propose(_request())
        assert seen["timeout"] == {
            "connect": 10.0,
            "read": 60.0,
            "write": 60.0,
            "pool": 60.0,
        }


# --- success -------------------------------------------------------------------------------------


class TestSuccessfulCall:
    async def test_a_valid_response_becomes_a_typed_artifact_with_usage(self) -> None:
        transport = returning_artifact("propose", input_tokens=411, output_tokens=222)
        result = await _provider(transport=transport).propose(_request())
        assert isinstance(result, ProviderResult)
        assert isinstance(result.artifact, ProposalArtifact)
        assert result.usage is not None
        assert result.usage.input_tokens == 411
        assert result.usage.output_tokens == 222
        assert result.usage.provider_request_id == "msg_test_0001"
        assert result.usage.model_name == "claude-sonnet-5"
        assert result.usage.call_occurred is True
        assert transport.call_count == 1

    async def test_the_estimate_that_gated_the_spend_travels_with_the_result(self) -> None:
        evaluator = FakeBudgetEvaluator()
        transport = returning_artifact("propose")
        result = await _provider(transport=transport, evaluator=evaluator).propose(_request())
        assert result.usage is not None
        assert result.usage.estimated_cost_usd == pytest.approx(
            evaluator.preflights[0]["estimated_cost_usd"]
        )

    async def test_decompose_plan_returns_a_bounded_plan(self) -> None:
        transport = returning_artifact("decompose_plan")
        result = await _provider(transport=transport).decompose_plan(
            _request("decompose_plan", context={"goal_statement": "ship"})
        )
        assert isinstance(result.artifact, PlanDraftArtifact)
        assert len(result.artifact.plan.steps) == 2


# --- malicious and malformed output ------------------------------------------------------------------


class TestStrictParsing:
    async def _refuses(self, transport: object, verb: str = "propose") -> LiveProviderError:
        provider = _provider(transport=transport)
        with pytest.raises(LiveProviderError) as caught:
            await getattr(provider, verb)(_request(verb, context=_plan_context(verb)))
        return caught.value

    async def test_a_markdown_fence_is_not_stripped(self) -> None:
        """Stripping a fence until parsing succeeds is repair, and repair accepts output the model
        was explicitly told not to produce."""
        body = "```json\n" + json.dumps(valid_artifact_json("propose")) + "\n```"
        error = await self._refuses(returning_text(body))
        assert error.failure_category == "malformed_output"

    async def test_invalid_json_is_terminal(self) -> None:
        error = await self._refuses(returning_text("{not json at all"))
        assert error.failure_category == "malformed_output"

    async def test_a_json_array_is_not_an_artifact(self) -> None:
        error = await self._refuses(returning_text(json.dumps([1, 2, 3])))
        assert error.failure_category == "malformed_output"

    async def test_no_regex_extraction_of_an_embedded_object(self) -> None:
        body = "Here is my answer: " + json.dumps(valid_artifact_json("propose"))
        error = await self._refuses(returning_text(body))
        assert error.failure_category == "malformed_output"

    async def test_a_missing_required_field_is_terminal(self) -> None:
        payload = valid_artifact_json("propose")
        del payload["recommendation"]
        error = await self._refuses(returning_text(json.dumps(payload)))
        assert error.failure_category == "malformed_output"

    async def test_an_extra_field_is_refused_by_the_closed_schema(self) -> None:
        payload = {**valid_artifact_json("propose"), "chain_of_thought": "step 1..."}
        error = await self._refuses(returning_text(json.dumps(payload)))
        assert error.failure_category == "malformed_output"

    async def test_a_secret_shaped_key_never_becomes_an_artifact(self) -> None:
        payload = {**valid_artifact_json("propose"), "api_key": "sk-ant-not-real"}
        error = await self._refuses(returning_text(json.dumps(payload)))
        assert error.failure_category == "malformed_output"

    async def test_an_empty_content_block_is_terminal(self) -> None:
        error = await self._refuses(responding(anthropic_body("")))
        assert error.failure_category == "malformed_output"

    async def test_a_body_that_is_not_an_object_is_terminal(self) -> None:
        error = await self._refuses(responding(["not", "a", "message"]))
        assert error.failure_category == "malformed_output"


def _plan_context(verb: str) -> dict[str, object]:
    if verb == "decompose_plan":
        return {"goal_statement": "ship", "acceptance_criteria": ["a"]}
    return _context()


class TestPlanBoundsAreEnforcedOnLiveOutput:
    async def _plan_refusal(self, plan: dict[str, object]) -> LiveProviderError:
        payload = {**valid_artifact_json("decompose_plan"), "plan": plan}
        provider = _provider(transport=returning_text(json.dumps(payload)))
        with pytest.raises(LiveProviderError) as caught:
            await provider.decompose_plan(
                _request("decompose_plan", context=_plan_context("decompose_plan"))
            )
        return caught.value

    async def test_forty_one_steps_is_refused(self) -> None:
        plan = {
            "objective": "o",
            "steps": [{"step_key": f"s{i}", "title": "t"} for i in range(41)],
        }
        assert (await self._plan_refusal(plan)).failure_category == "malformed_output"

    async def test_forty_steps_is_accepted(self) -> None:
        plan = {
            "objective": "o",
            "steps": [{"step_key": f"s{i}", "title": "t"} for i in range(40)],
        }
        payload = {**valid_artifact_json("decompose_plan"), "plan": plan}
        provider = _provider(transport=returning_text(json.dumps(payload)))
        result = await provider.decompose_plan(
            _request("decompose_plan", context=_plan_context("decompose_plan"))
        )
        assert len(result.artifact.plan.steps) == 40

    @pytest.mark.parametrize(
        "field", ["depends_on", "required_capabilities", "expected_outputs", "constraints"]
    )
    async def test_eleven_entries_in_a_per_step_list_is_refused(self, field: str) -> None:
        overflow = (
            [f"s{i}" for i in range(11)] if field == "depends_on" else [f"v{i}" for i in range(11)]
        )
        steps = [{"step_key": f"s{i}", "title": "t"} for i in range(12)]
        steps[11][field] = overflow
        plan = {"objective": "o", "steps": steps}
        assert (await self._plan_refusal(plan)).failure_category == "malformed_output"


class TestArtifactSizeBackstop:
    async def test_an_oversized_artifact_never_becomes_a_result(self) -> None:
        """The control the token cap cannot provide: a provider that ignored max_tokens entirely.

        ``PlanContent.constraints`` is bounded neither in count nor in item length, so a plan can be
        schema-valid and still be enormous -- which is exactly why the byte bound is independent of
        the step bound rather than derived from it.
        """
        plan = {"objective": "o", "steps": [], "constraints": ["x" * (MAX_ARTIFACT_BYTES + 1000)]}
        payload = {**valid_artifact_json("decompose_plan"), "plan": plan}
        provider = _provider(transport=returning_text(json.dumps(payload)))
        with pytest.raises(LiveProviderError) as caught:
            await provider.decompose_plan(
                _request("decompose_plan", context=_plan_context("decompose_plan"))
            )
        assert caught.value.failure_category == "malformed_output"
        assert "exceeds the durable maximum" in str(caught.value)


# --- HTTP failures ---------------------------------------------------------------------------------


class TestHttpFailureMapping:
    @pytest.mark.parametrize(
        "status,category",
        [
            (429, "rate_limited"),
            (500, "provider_unavailable"),
            (503, "provider_unavailable"),
            (401, "provider_unauthorized"),
            (403, "provider_unauthorized"),
            (404, "provider_unauthorized"),
            (400, "provider_unauthorized"),
        ],
    )
    async def test_status_maps_to_the_canonical_category(self, status: int, category: str) -> None:
        transport = responding({"error": {"message": "provider said so"}}, status_code=status)
        provider = _provider(transport=transport)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == category

    async def test_the_provider_error_body_is_never_echoed(self) -> None:
        """A provider's error body is untrusted text. Only the status code -- a bounded integer --
        reaches the failure reason."""
        leak = "sk-ant-LEAKED-KEY and the whole prompt echoed back"
        transport = responding({"error": {"message": leak}}, status_code=400)
        provider = _provider(transport=transport)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert leak not in str(caught.value)
        assert "sk-ant" not in str(caught.value)
        assert "HTTP 400" in str(caught.value)

    async def test_a_transport_error_is_unavailable_and_carries_only_a_class_name(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused to 10.0.0.1 with token abc")

        provider = _provider(transport=httpx.MockTransport(handler))
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "provider_unavailable"
        assert "ConnectError" in str(caught.value)
        assert "10.0.0.1" not in str(caught.value)
        assert "token abc" not in str(caught.value)


class TestTimeout:
    async def test_a_slow_provider_becomes_provider_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(adapter_module, "ATTEMPT_TIMEOUT_SECONDS", 0.15)
        transport = SlowTransport(delay=5.0)
        provider = _provider(transport=transport)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "provider_timeout"
        assert transport.completed == 0

    async def test_the_event_loop_stays_free_while_the_provider_is_slow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reason the provider contract had to become awaitable.

        A blocking HTTP call inside an ``async def`` stops the orchestrator's whole event loop for
        the duration of the request timeout, so one slow reasoning call would freeze every other
        request the process is serving. The heartbeat is what proves it does not.
        """
        monkeypatch.setattr(adapter_module, "ATTEMPT_TIMEOUT_SECONDS", 0.4)
        ticks = 0

        async def heartbeat() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        beat = asyncio.create_task(heartbeat())
        try:
            provider = _provider(transport=SlowTransport(delay=5.0))
            with pytest.raises(LiveProviderError):
                await provider.propose(_request())
        finally:
            beat.cancel()
        assert ticks >= 10


# --- budget ---------------------------------------------------------------------------------------


class TestBudget:
    async def test_an_allowed_preflight_lets_the_call_run(self) -> None:
        evaluator = FakeBudgetEvaluator()
        transport = returning_artifact("propose")
        await _provider(transport=transport, evaluator=evaluator).propose(_request())
        assert transport.call_count == 1
        assert evaluator.preflights[0]["provider"] == "anthropic"
        assert evaluator.preflights[0]["model_name"] == "claude-sonnet-5"

    async def test_the_completion_estimate_assumes_the_whole_allowance(self) -> None:
        """The only completion count knowable before the call. Assuming less would let a gate pass
        on an estimate the call can legitimately exceed."""
        evaluator = FakeBudgetEvaluator()
        await _provider(
            transport=returning_artifact("decompose_plan"), evaluator=evaluator
        ).decompose_plan(_request("decompose_plan", context=_plan_context("decompose_plan")))
        assert evaluator.preflights[0]["completion_tokens"] == 4000

    async def test_a_refused_preflight_makes_zero_provider_calls(self) -> None:
        transport = returning_artifact("propose")
        provider = _provider(transport=transport, evaluator=blocked_evaluator())
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "budget_exceeded"
        assert transport.call_count == 0

    async def test_no_active_policy_makes_zero_provider_calls(self) -> None:
        transport = returning_artifact("propose")
        provider = _provider(transport=transport, evaluator=FakeBudgetEvaluator(policy=None))
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "budget_exceeded"
        assert "no active LLM budget policy" in str(caught.value)
        assert transport.call_count == 0

    @pytest.mark.parametrize("missing", ["max_cost_per_day_usd", "max_cost_per_month_usd"])
    async def test_a_policy_without_both_aggregate_caps_is_refused(self, missing: str) -> None:
        """A policy that bounds one call but not a thousand of them is not a bound on live mode."""
        policy = FakePolicy(**{missing: None})  # type: ignore[arg-type]
        transport = returning_artifact("propose")
        provider = _provider(transport=transport, evaluator=FakeBudgetEvaluator(policy=policy))
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "budget_exceeded"
        assert transport.call_count == 0

    async def test_the_per_call_ceiling_is_enforced_independently_of_the_policy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The operator's policy bounds the account; this bounds any ONE call."""
        monkeypatch.setattr(adapter_module, "MAX_COST_PER_CALL_USD", 0.0000001)
        transport = returning_artifact("propose")
        provider = _provider(transport=transport)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "budget_exceeded"
        assert "per-call maximum" in str(caught.value)
        assert transport.call_count == 0

    async def test_a_realistic_call_sits_far_below_the_ceiling(self) -> None:
        evaluator = FakeBudgetEvaluator()
        await _provider(transport=returning_artifact("propose"), evaluator=evaluator).propose(
            _request()
        )
        assert evaluator.preflights[0]["estimated_cost_usd"] < MAX_COST_PER_CALL_USD / 10

    async def test_usage_is_recorded_even_when_the_response_is_unusable(self) -> None:
        """A call that reached the provider is billable whatever the body turns out to contain."""
        evaluator = FakeBudgetEvaluator()
        transport = returning_text("{not json", input_tokens=350, output_tokens=90)
        provider = _provider(transport=transport, evaluator=evaluator)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "malformed_output"
        assert caught.value.usage is not None
        assert caught.value.usage.input_tokens == 350
        assert evaluator.usages == [
            {
                "provider": "anthropic",
                "model_name": "claude-sonnet-5",
                "prompt_tokens": 350,
                "completion_tokens": 90,
                "policy_id": "policy-test",
                "metadata": {"provider_request_id": "msg_test_0001"},
            }
        ]

    async def test_a_ledger_failure_does_not_discard_a_paid_valid_result(self) -> None:
        """The money is already spent; failing the call to record that it was spent helps nobody."""

        class _BrokenLedger(FakeBudgetEvaluator):
            async def record_usage(self, **kwargs: object) -> dict[str, object]:
                raise RuntimeError("ledger unavailable")

        result = await _provider(
            transport=returning_artifact("propose"), evaluator=_BrokenLedger()
        ).propose(_request())
        assert isinstance(result.artifact, ProposalArtifact)


# --- secrets ---------------------------------------------------------------------------------------


class TestCredential:
    async def test_a_missing_credential_fails_closed_without_calling_anybody(self) -> None:
        transport = returning_artifact("propose")
        provider = _provider(transport=transport, secrets=FakeSecretProvider(present=False))
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "provider_unauthorized"
        assert transport.call_count == 0

    async def test_the_secret_is_read_last_and_only_once(self) -> None:
        secrets = FakeSecretProvider()
        await _provider(transport=returning_artifact("propose"), secrets=secrets).propose(
            _request()
        )
        assert secrets.lookups == [ANTHROPIC_SECRET_NAME]

    async def test_a_closed_gate_refuses_before_any_secret_is_read(self) -> None:
        """AT-M3.6B.1 section 9. Reading Vault to discover live calls are disabled would touch a
        secret backend for nothing and make the disabled path depend on it being reachable."""
        secrets = ExplodingSecretProvider()
        transport = returning_artifact("propose")
        provider = _provider(transport=transport, enabled=False, secrets=secrets)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "provider_disabled"
        assert secrets.lookups == []
        assert transport.call_count == 0

    async def test_an_unauthorized_model_refuses_before_any_secret_is_read(self) -> None:
        secrets = ExplodingSecretProvider()
        transport = returning_artifact("propose")
        provider = _provider(transport=transport, model="claude-3-opus", secrets=secrets)
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(_request())
        assert caught.value.failure_category == "provider_unauthorized"
        assert secrets.lookups == []
        assert transport.call_count == 0

    async def test_the_credential_is_never_validated_against_the_provider(self) -> None:
        """AT-M3.6B.1 section 49: secret correctness is not checked by calling Anthropic."""
        transport = returning_artifact("propose")
        provider = _provider(
            transport=transport, secrets=FakeSecretProvider(value="obviously-wrong")
        )
        await provider.preflight(_request())
        assert transport.call_count == 0


# --- pre-flight ---------------------------------------------------------------------------------------


class TestPreflight:
    async def test_preflight_refuses_a_closed_gate_without_touching_the_network(self) -> None:
        transport = returning_artifact("propose")
        provider = _provider(transport=transport, enabled=False)
        with pytest.raises(LiveProviderError) as caught:
            await provider.preflight(_request())
        assert caught.value.failure_category == "provider_disabled"
        assert transport.call_count == 0

    async def test_preflight_passes_for_a_fully_authorized_posture(self) -> None:
        transport = returning_artifact("propose")
        assert await _provider(transport=transport).preflight(_request()) is None
        assert transport.call_count == 0

    async def test_preflight_refuses_an_oversized_context(self) -> None:
        transport = returning_artifact("propose")
        provider = _provider(transport=transport)
        oversized = {**_context(), "goal_statement": "x" * 40000}
        with pytest.raises(LiveProviderError) as caught:
            await provider.preflight(_request(context=oversized))
        assert caught.value.failure_category == "provider_unauthorized"
        assert transport.call_count == 0
