"""Step AT-M3.6B.1 -- ReasoningService driving the live adapter, against the in-memory store.

The claims here are about the SERVICE's contract once a provider can be live: that replay never
reaches a provider, that a refusal is recorded rather than thrown, that usage survives onto the
durable row on both outcomes, and that the attempt_token guard still decides which of two live
attempts is canonical.

The store is the AT-M3.1 in-memory fake, which mirrors the real one's ownership, lease and
success-artifact semantics; the ownership behaviour it models is exercised against real PostgreSQL
in the concurrency suite. No network: every provider call goes through an in-process transport.
"""

from __future__ import annotations

import asyncio

import pytest

from shared.sdk.agent_reasoning.models import ProposalArtifact, ReasoningRequest
from shared.sdk.agent_reasoning.service import ReasoningService
from tests.agent_reasoning_fakes import InMemoryReasoningInvocationStore
from tests.at_m3_6b_1_fakes import (
    FAKE_API_KEY,
    ExplodingSecretProvider,
    FakeBudgetEvaluator,
    FakeSecretProvider,
    GatedTransport,
    anthropic_body,
    live_config,
    returning_artifact,
    returning_text,
    valid_artifact_json,
)
from shared.sdk.agent_reasoning.anthropic_provider import AnthropicReasoningProvider

pytestmark = pytest.mark.asyncio


def _context() -> dict[str, object]:
    return {
        "topic": "sequence the work",
        "round": 1,
        "goal_statement": "ship the adapter",
        "recent_messages": [{"message_type": "proposal", "summary": "start small"}],
    }


def _request(**overrides: object) -> ReasoningRequest:
    payload: dict[str, object] = {"verb": "propose", "context": _context()}
    payload.update(overrides)
    return ReasoningRequest(**payload)  # type: ignore[arg-type]


def _adapter(
    transport: object,
    *,
    enabled: bool = True,
    secrets: object | None = None,
    evaluator: object | None = None,
) -> AnthropicReasoningProvider:
    return AnthropicReasoningProvider(
        config=live_config(enabled=enabled),
        secret_provider=secrets if secrets is not None else FakeSecretProvider(),
        budget_evaluator=evaluator if evaluator is not None else FakeBudgetEvaluator(),
        transport=transport,
    )


class TestFreshLiveInvocation:
    async def test_a_live_success_records_provider_identity_and_usage(self) -> None:
        store = InMemoryReasoningInvocationStore()
        transport = returning_artifact("propose", input_tokens=500, output_tokens=250)
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport)
        )

        assert result.disposition == "fresh"
        assert isinstance(result.artifact, ProposalArtifact)
        row = result.invocation
        assert row["status"] == "succeeded"
        assert row["provider_mode"] == "live"
        assert row["model_name"] == "claude-sonnet-5"
        assert row["input_tokens"] == 500
        assert row["output_tokens"] == 250
        assert row["estimated_cost_usd"] is not None
        assert row["artifact_type"] == "ProposalArtifact"
        assert transport.call_count == 1

    async def test_the_request_cannot_reroute_the_provider_or_the_model(self) -> None:
        """A hostile request is recorded truthfully and changes nothing about what ran."""
        store = InMemoryReasoningInvocationStore()
        transport = returning_artifact("propose")
        result = await ReasoningService(store=store).invoke(
            _request(provider_name="expensive-other-provider", model_name="other-model"),
            provider=_adapter(transport),
        )
        row = result.invocation
        # What was ASKED for is preserved as evidence...
        assert row["requested_provider_name"] == "expensive-other-provider"
        # ...and what actually RAN is the configured provider and model.
        assert row["provider_mode"] == "live"
        assert row["model_name"] == "claude-sonnet-5"
        assert transport.payload()["model"] == "claude-sonnet-5"

    async def test_the_awaitable_verb_is_awaited_rather_than_stored_as_a_coroutine(self) -> None:
        store = InMemoryReasoningInvocationStore()
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(returning_artifact("propose"))
        )
        assert isinstance(result.artifact, ProposalArtifact)
        assert not asyncio.iscoroutine(result.artifact)


class TestReplayNeverReachesAProvider:
    async def test_a_second_call_replays_without_calling_anybody(self) -> None:
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        transport = returning_artifact("propose")
        secrets = FakeSecretProvider()
        adapter = _adapter(transport, secrets=secrets)
        evaluator = adapter._budget_evaluator

        request = _request()
        first = await service.invoke(request, provider=adapter)
        second = await service.invoke(request, provider=adapter)

        assert first.disposition == "fresh"
        assert second.disposition == "replay"
        assert second.artifact == first.artifact
        assert transport.call_count == 1
        assert len(secrets.lookups) == 1
        assert len(evaluator.preflights) == 1
        assert len(evaluator.usages) == 1

    async def test_replay_works_with_the_live_gate_closed_and_no_secret_available(self) -> None:
        """The load-bearing one.

        Work that is already done and already paid for must stay recoverable when the live path is
        switched off -- which, throughout AT-M3.6B.1, it always is. If replay resolved the provider
        first, every historical artifact would become unreadable the moment the gate closed.
        """
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        request = _request()
        await service.invoke(request, provider=_adapter(returning_artifact("propose")))

        disabled_transport = returning_artifact("propose")
        replayed = await service.invoke(
            request,
            provider=_adapter(disabled_transport, enabled=False, secrets=ExplodingSecretProvider()),
        )
        assert replayed.disposition == "replay"
        assert isinstance(replayed.artifact, ProposalArtifact)
        assert disabled_transport.call_count == 0

    async def test_replay_does_not_even_resolve_a_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Section 15: zero provider RESOLUTION, not merely zero provider call."""
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        request = _request()
        await service.invoke(request, provider=_adapter(returning_artifact("propose")))

        import shared.sdk.agent_reasoning.service as service_module

        def _explode(_name: object = None) -> object:  # pragma: no cover - must never run
            raise AssertionError("replay must not resolve a provider")

        monkeypatch.setattr(service_module, "get_reasoning_provider", _explode)
        replayed = await service.invoke(request)
        assert replayed.disposition == "replay"
        assert isinstance(replayed.artifact, ProposalArtifact)


class TestRefusalsAreRecordedNotThrown:
    async def test_a_closed_gate_produces_a_durable_failed_invocation(self) -> None:
        store = InMemoryReasoningInvocationStore()
        transport = returning_artifact("propose")
        result = await ReasoningService(store=store).invoke(
            _request(),
            provider=_adapter(transport, enabled=False, secrets=ExplodingSecretProvider()),
        )
        assert result.disposition == "fresh"
        assert result.artifact is None
        row = result.invocation
        assert row["status"] == "failed"
        assert row["failure_category"] == "provider_disabled"
        assert row["artifact"] is None
        assert transport.call_count == 0

    async def test_a_budget_refusal_is_recorded_as_budget_exceeded(self) -> None:
        store = InMemoryReasoningInvocationStore()
        transport = returning_artifact("propose")
        result = await ReasoningService(store=store).invoke(
            _request(),
            provider=_adapter(transport, evaluator=FakeBudgetEvaluator(policy=None)),
        )
        assert result.invocation["failure_category"] == "budget_exceeded"
        assert transport.call_count == 0

    async def test_a_misconfigured_model_can_never_produce_a_succeeded_row(self) -> None:
        """A refused attempt records the model it was CONFIGURED for -- that is the diagnostic an
        operator needs -- but it can never be a success, so no durable artifact is ever attributable
        to a model outside the allowlist."""
        from shared.sdk.agent_reasoning.live_config import LiveReasoningConfig

        store = InMemoryReasoningInvocationStore()
        transport = returning_artifact("propose")
        adapter = AnthropicReasoningProvider(
            config=LiveReasoningConfig(
                provider_name="anthropic",
                model_name="claude-3-opus",
                live_network_enabled=True,
            ),
            secret_provider=ExplodingSecretProvider(),
            budget_evaluator=FakeBudgetEvaluator(),
            transport=transport,
        )
        result = await ReasoningService(store=store).invoke(_request(), provider=adapter)

        row = result.invocation
        assert row["status"] == "failed"
        assert row["failure_category"] == "provider_unauthorized"
        assert row["artifact"] is None
        assert row["model_name"] == "claude-3-opus"
        assert transport.call_count == 0

    async def test_an_unapproved_egress_field_never_reaches_a_provider(self) -> None:
        store = InMemoryReasoningInvocationStore()
        transport = returning_artifact("propose")
        result = await ReasoningService(store=store).invoke(
            _request(context={**_context(), "other_project_note": "leak"}),
            provider=_adapter(transport),
        )
        assert result.invocation["failure_category"] == "provider_unauthorized"
        assert transport.call_count == 0

    async def test_a_malformed_response_fails_but_keeps_its_usage(self) -> None:
        """The call happened and is billable; a failed row that dropped its tokens would make the
        audit trail cheaper than the invoice."""
        store = InMemoryReasoningInvocationStore()
        transport = returning_text("not json", input_tokens=310, output_tokens=15)
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport)
        )
        row = result.invocation
        assert row["status"] == "failed"
        assert row["failure_category"] == "malformed_output"
        assert row["input_tokens"] == 310
        assert row["output_tokens"] == 15
        assert row["artifact"] is None

    @pytest.mark.parametrize(
        "status,category",
        [(429, "rate_limited"), (500, "provider_unavailable"), (401, "provider_unauthorized")],
    )
    async def test_live_failure_categories_reach_the_durable_row(
        self, status: int, category: str
    ) -> None:
        from tests.at_m3_6b_1_fakes import responding

        store = InMemoryReasoningInvocationStore()
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(responding({"error": "x"}, status_code=status))
        )
        assert result.invocation["failure_category"] == category


class TestZombieAttempt:
    async def test_a_superseded_live_attempt_cannot_overwrite_the_canonical_artifact(self) -> None:
        """Attempt 1 is slow, its lease expires, attempt 2 takes over and wins, attempt 1 returns.

        Both attempts really called a provider -- that is at-least-once external attempts, stated
        honestly -- and exactly one artifact is canonical.
        """
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        request = _request()

        slow = GatedTransport(
            body=anthropic_body(valid_artifact_json("propose"), message_id="msg_zombie")
        )
        first = asyncio.create_task(service.invoke(request, provider=_adapter(slow)))
        await slow.arrived.wait()

        # The first worker is now inside its provider call. Its lease expires and a second worker
        # takes the attempt over and finishes.
        store.expire_lease(str(request.correlation_id))
        fast = returning_artifact("propose", message_id="msg_winner")
        winner = await service.invoke(request, provider=_adapter(fast))
        assert winner.disposition == "fresh"
        assert winner.invocation["attempt"] == 2

        slow.release()
        loser = await first

        assert slow.call_count == 1
        assert fast.call_count == 1
        # The zombie learns it lost and is handed the canonical row rather than an error.
        assert loser.disposition == "replay"
        assert loser.invocation["invocation_id"] == winner.invocation["invocation_id"]
        assert loser.invocation["attempt"] == 2

        canonical = await store.get_by_correlation_id(str(request.correlation_id))
        assert canonical is not None
        assert canonical["status"] == "succeeded"
        assert canonical["attempt"] == 2
        assert canonical["artifact"] == winner.invocation["artifact"]

    async def test_the_attempt_token_is_never_exposed_to_a_caller(self) -> None:
        store = InMemoryReasoningInvocationStore()
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(returning_artifact("propose"))
        )
        assert "attempt_token" not in (result.artifact.model_dump() if result.artifact else {})


class TestNoSecretEverReachesDurableState:
    async def test_the_api_key_is_absent_from_the_whole_invocation_row(self) -> None:
        store = InMemoryReasoningInvocationStore()
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(returning_artifact("propose"))
        )
        rendered = repr(result.invocation)
        assert FAKE_API_KEY not in rendered
        assert "x-api-key" not in rendered

    async def test_a_provider_error_carrying_a_key_shape_is_sanitized(self) -> None:
        """The provider's error body is never echoed, so a key-shaped string in it cannot survive."""
        from tests.at_m3_6b_1_fakes import responding

        leaked = "sk-ant-api03-THIS-IS-NOT-REAL-0123456789abcdef"
        store = InMemoryReasoningInvocationStore()
        result = await ReasoningService(store=store).invoke(
            _request(),
            provider=_adapter(responding({"error": {"message": leaked}}, status_code=400)),
        )
        assert leaked not in repr(result.invocation)
        assert result.invocation["failure_category"] == "provider_unauthorized"
