"""Step AT-M3.6B.1 remediation -- retryable failures actually retry.

AT-M3.6B.1 Independent Validation 1 found that ``provider_timeout``, ``rate_limited`` and
``provider_unavailable`` were declared retryable and behaved terminally: the first transient failure
wrote a FAILED row, and the next call for that correlation_id replayed it. The categories were
labels. These tests are the difference between a label and a behaviour.

WHAT IS ASSERTED, and why each one is here rather than assumed:

* a timeout, a 429 and a 5xx each progress attempt 1 -> attempt 2 and can then succeed;
* the progression is the SAME invocation -- one row, one correlation_id, an attempt that counts up
  and an attempt_token that rotates -- not a new correlation and not a second row;
* three attempts and no fourth, ever, whatever the provider keeps saying;
* a deterministic failure does not retry, because re-asking would spend money to fail identically;
* the retry authority is ``ReasoningService`` and only it: the adapter's transport is still
  constructed with ``retries=0``, so N attempts is exactly N provider calls and never a multiple;
* a KNOWN transient answer does not wait for the 120s lease to expire. Takeover recovers a worker
  that has gone silent; a provider that answered "429" has not gone silent, and making a discussion
  wait two minutes for an answer already in hand would be a defect of its own.

No network: every provider answer comes from an in-process transport, and the AT-M3.6B.1 network
guard fails this module if anything tries to open a non-loopback socket.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any

import pytest

from shared.sdk.agent_reasoning.anthropic_provider import AnthropicReasoningProvider
from shared.sdk.agent_reasoning.models import (
    RETRYABLE_FAILURE_CATEGORIES,
    ProposalArtifact,
    ReasoningRequest,
)
from shared.sdk.agent_reasoning.service import ReasoningService
from shared.sdk.agent_reasoning.store import ReasoningInvocationStore
from tests.agent_reasoning_fakes import InMemoryReasoningInvocationStore
from tests.at_m3_6b_1_fakes import (
    FakeBudgetEvaluator,
    FakeSecretProvider,
    SequencedTransport,
    anthropic_body,
    live_config,
    transient_then_artifact,
    valid_artifact_json,
)

pytestmark = pytest.mark.asyncio

_RATE_LIMITED = (429, {"type": "error", "error": {"type": "rate_limit_error"}})
_UNAVAILABLE = (503, {"type": "error", "error": {"type": "overloaded_error"}})


def _request(**overrides: Any) -> ReasoningRequest:
    payload: dict[str, Any] = {
        "verb": "propose",
        "context": {
            "topic": "sequence the work",
            "round": 1,
            "goal_statement": "ship the adapter",
            "recent_messages": [{"message_type": "proposal", "summary": "start small"}],
        },
    }
    payload.update(overrides)
    return ReasoningRequest(**payload)  # type: ignore[arg-type]


def _adapter(transport: Any, *, evaluator: Any | None = None) -> AnthropicReasoningProvider:
    return AnthropicReasoningProvider(
        config=live_config(),
        secret_provider=FakeSecretProvider(),
        budget_evaluator=evaluator if evaluator is not None else FakeBudgetEvaluator(),
        transport=transport,
    )


class TestATransientFailureProgressesToTheNextAttempt:
    """The load-bearing three. Each one used to terminalize on the first failure."""

    @pytest.mark.parametrize(
        "failure,expected_category",
        [
            ("timeout", "provider_timeout"),
            (_RATE_LIMITED, "rate_limited"),
            (_UNAVAILABLE, "provider_unavailable"),
        ],
        ids=["timeout", "rate_limited", "unavailable"],
    )
    async def test_one_transient_failure_then_success(
        self, failure: Any, expected_category: str
    ) -> None:
        assert expected_category in RETRYABLE_FAILURE_CATEGORIES
        store = InMemoryReasoningInvocationStore()
        transport = transient_then_artifact("propose", failure)
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport)
        )

        assert result.disposition == "fresh"
        assert isinstance(result.artifact, ProposalArtifact)
        assert result.invocation["status"] == "succeeded"
        # Two attempts, two provider calls, ONE canonical artifact.
        assert result.invocation["attempt"] == 2
        assert transport.call_count == 2
        assert len(store.rows_by_invocation) == 1

    async def test_the_retry_is_the_same_invocation_and_the_token_rotates(self) -> None:
        store = InMemoryReasoningInvocationStore()
        request = _request()
        transport = transient_then_artifact("propose", "timeout")

        # Capture attempt 1's identity before it is superseded.
        seen: list[tuple[str, int, str]] = []
        original = store.advance_retryable_attempt

        async def watching(invocation_id: Any, **kwargs: Any) -> Any:
            before = store.rows_by_invocation[str(invocation_id)]
            seen.append(
                (str(before["invocation_id"]), int(before["attempt"]), str(before["attempt_token"]))
            )
            return await original(invocation_id, **kwargs)

        store.advance_retryable_attempt = watching  # type: ignore[method-assign]
        result = await ReasoningService(store=store).invoke(request, provider=_adapter(transport))

        assert len(seen) == 1
        before_id, before_attempt, before_token = seen[0]
        row = result.invocation
        assert str(row["invocation_id"]) == before_id, "a retry must not create a second row"
        assert str(row["correlation_id"]) == str(request.correlation_id)
        assert before_attempt == 1 and row["attempt"] == 2
        assert str(row["attempt_token"]) != before_token, "the attempt token must rotate"

    async def test_a_known_transient_answer_does_not_wait_for_the_lease(self) -> None:
        """The retry happens on the provider's answer, not on a 120-second timer.

        Takeover is crash recovery: it waits out a lease because a silent worker gives it nothing
        else to go on. A provider that returned 429 gave us something to go on, and blocking a
        discussion for two minutes on an answer already in hand would trade one defect for another.
        """
        store = InMemoryReasoningInvocationStore(lease_ttl_seconds=120)
        transport = transient_then_artifact("propose", _RATE_LIMITED)
        started = time.monotonic()
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport)
        )
        elapsed = time.monotonic() - started

        assert result.invocation["attempt"] == 2
        assert elapsed < 5.0, f"the retry waited {elapsed:.1f}s; the lease was not the trigger"
        # And nothing extended the lease to buy time.
        assert store.lease_ttl_seconds == 120


class TestExhaustion:
    async def test_three_transient_failures_terminalize_and_there_is_no_fourth_call(self) -> None:
        store = InMemoryReasoningInvocationStore()
        transport = SequencedTransport(["timeout", "timeout", "timeout"])
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport)
        )

        assert result.invocation["status"] == "failed"
        assert result.invocation["failure_category"] == "provider_timeout"
        assert result.invocation["attempt"] == 3
        assert result.invocation["artifact"] is None
        # The script has exactly three steps and raises on a fourth request, so this is proof
        # rather than a count that happens to agree.
        assert transport.call_count == 3

    async def test_the_final_category_is_the_final_attempt_s_own_outcome(self) -> None:
        """Exhaustion reports what actually happened last, not a synthetic 'gave up' category."""
        store = InMemoryReasoningInvocationStore()
        transport = SequencedTransport(["timeout", _RATE_LIMITED, _UNAVAILABLE])
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport)
        )
        assert result.invocation["failure_category"] == "provider_unavailable"
        assert transport.call_count == 3

    async def test_an_exhausted_invocation_replays_rather_than_attempting_a_fourth_time(
        self,
    ) -> None:
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        request = _request()
        transport = SequencedTransport(["timeout", "timeout", "timeout"])
        adapter = _adapter(transport)

        first = await service.invoke(request, provider=adapter)
        second = await service.invoke(request, provider=adapter)

        assert first.invocation["status"] == "failed"
        assert second.disposition == "replay"
        assert transport.call_count == 3


class TestDeterministicFailuresDoNotRetry:
    async def test_malformed_output_is_terminal_after_one_call(self) -> None:
        store = InMemoryReasoningInvocationStore()
        transport = SequencedTransport([(200, anthropic_body("{not json"))])
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport)
        )
        assert result.invocation["status"] == "failed"
        assert result.invocation["failure_category"] == "malformed_output"
        assert result.invocation["attempt"] == 1
        assert transport.call_count == 1

    @pytest.mark.parametrize("status", [400, 401, 403, 404])
    async def test_a_deterministic_http_rejection_is_terminal_after_one_call(
        self, status: int
    ) -> None:
        store = InMemoryReasoningInvocationStore()
        transport = SequencedTransport([(status, {"type": "error"})])
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport)
        )
        assert result.invocation["failure_category"] == "provider_unauthorized"
        assert result.invocation["attempt"] == 1
        assert transport.call_count == 1

    async def test_a_budget_refusal_is_terminal_with_zero_calls(self) -> None:
        from tests.at_m3_6b_1_fakes import blocked_evaluator

        store = InMemoryReasoningInvocationStore()
        transport = SequencedTransport([(200, anthropic_body(valid_artifact_json("propose")))])
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport, evaluator=blocked_evaluator())
        )
        assert result.invocation["status"] == "failed"
        assert result.invocation["failure_category"] == "budget_exceeded"
        assert result.invocation["attempt"] == 1
        assert transport.call_count == 0

    async def test_a_closed_gate_is_terminal_with_zero_calls(self) -> None:
        store = InMemoryReasoningInvocationStore()
        transport = SequencedTransport([(200, anthropic_body(valid_artifact_json("propose")))])
        adapter = AnthropicReasoningProvider(
            config=live_config(enabled=False),
            secret_provider=FakeSecretProvider(),
            budget_evaluator=FakeBudgetEvaluator(),
            transport=transport,
        )
        result = await ReasoningService(store=store).invoke(_request(), provider=adapter)
        assert result.invocation["failure_category"] == "provider_disabled"
        assert result.invocation["attempt"] == 1
        assert transport.call_count == 0

    async def test_the_store_primitive_itself_refuses_a_deterministic_category(self) -> None:
        """Belt and braces: even a caller that bypassed the service could not retry a parse error."""
        store = InMemoryReasoningInvocationStore()
        _, row = await store.try_begin_invocation(
            {
                "reasoning_verb": "propose",
                "requested_provider_name": "anthropic",
                "provider_mode": "live",
                "correlation_id": str(uuid.uuid4()),
                "started_at": None,
            }
        )
        advanced = await store.advance_retryable_attempt(
            row["invocation_id"],
            attempt_token=row["attempt_token"],
            failure_category="malformed_output",
        )
        assert advanced is None


class TestNoRetryStacking:
    async def test_attempts_and_provider_calls_are_one_to_one(self) -> None:
        """The adapter and its transport add no retries of their own, so N attempts is N calls."""
        for failures, expected in ((0, 1), (1, 2), (2, 3)):
            store = InMemoryReasoningInvocationStore()
            transport = transient_then_artifact("propose", *(["timeout"] * failures))
            result = await ReasoningService(store=store).invoke(
                _request(), provider=_adapter(transport)
            )
            assert result.invocation["attempt"] == expected
            assert transport.call_count == expected

    async def test_the_adapter_transport_still_declares_zero_retries(self) -> None:
        import httpx

        captured: dict[str, Any] = {}

        class _Capturing(httpx.AsyncHTTPTransport):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured.update(kwargs)
                super().__init__(*args, **kwargs)

            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("never dialled", request=request)

        monkey = httpx.AsyncHTTPTransport
        httpx.AsyncHTTPTransport = _Capturing  # type: ignore[misc]
        try:
            provider = AnthropicReasoningProvider(
                config=live_config(),
                secret_provider=FakeSecretProvider(),
                budget_evaluator=FakeBudgetEvaluator(),
            )
            with pytest.raises(Exception):
                await provider.propose(_request())
        finally:
            httpx.AsyncHTTPTransport = monkey  # type: ignore[misc]
        assert captured.get("retries") == 0


class TestConcurrentRetry:
    async def test_eight_racers_produce_one_attempt_chain(self) -> None:
        """Only the canonical owner advances the attempt, so a retry is not multiplied by callers.

        Seven of the eight never own the invocation and therefore never call anybody -- which is
        the property that makes the retry loop safe to put inside ``invoke`` rather than behind a
        scheduler. The owner's own loop supplies attempt 2 and attempt 3.
        """
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        request = _request()
        transport = transient_then_artifact("propose", "timeout", _RATE_LIMITED)
        adapter = _adapter(transport)

        results = await asyncio.gather(
            *(service.invoke(request, provider=adapter) for _ in range(8))
        )

        fresh = [r for r in results if r.disposition == "fresh"]
        assert len(fresh) == 1, "exactly one caller may own the invocation"
        assert fresh[0].invocation["attempt"] == 3
        assert transport.call_count == 3, "three attempts, three calls, not eight"
        assert len(store.rows_by_invocation) == 1
        assert {r.invocation["invocation_id"] for r in results} == {
            fresh[0].invocation["invocation_id"]
        }


# --- the store primitive, against real PostgreSQL ----------------------------------------------


def _dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")


async def _live_store() -> ReasoningInvocationStore:
    import asyncpg

    try:
        conn = await asyncpg.connect(dsn=_dsn(), timeout=5)
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping the durable retry-transition tests")
    await conn.close()
    return ReasoningInvocationStore(_dsn())


async def _claim(store: ReasoningInvocationStore) -> dict[str, Any]:
    from datetime import datetime, timezone

    owned, row = await store.try_begin_invocation(
        {
            "reasoning_verb": "propose",
            "requested_provider_name": "anthropic",
            "provider_mode": "live",
            "model_name": "claude-sonnet-5",
            "correlation_id": str(uuid.uuid4()),
            "started_at": datetime.now(timezone.utc),
        }
    )
    assert owned
    return row


class TestDurableRetryTransition:
    async def test_the_transition_is_atomic_and_only_the_owner_wins(self) -> None:
        store = await _live_store()
        row = await _claim(store)

        first = await store.advance_retryable_attempt(
            row["invocation_id"],
            attempt_token=row["attempt_token"],
            failure_category="provider_timeout",
        )
        assert first is not None
        assert first["attempt"] == 2
        assert str(first["attempt_token"]) != str(row["attempt_token"])
        assert first["status"] == "started"
        assert str(first["correlation_id"]) == str(row["correlation_id"])
        assert str(first["invocation_id"]) == str(row["invocation_id"])
        # A 'started' row carries no outcome -- 037's status-consistency CHECK requires it, so the
        # attempt's failure evidence lives in the audit trail and the budget ledger, not here.
        assert first["failure_category"] is None
        assert first["failure_reason"] is None
        assert first["lease_expires_at"] is not None

        # The superseded owner cannot restart anything.
        again = await store.advance_retryable_attempt(
            row["invocation_id"],
            attempt_token=row["attempt_token"],
            failure_category="provider_timeout",
        )
        assert again is None

    async def test_eight_contenders_advance_the_attempt_exactly_once(self) -> None:
        store = await _live_store()
        row = await _claim(store)

        outcomes = await asyncio.gather(
            *(
                store.advance_retryable_attempt(
                    row["invocation_id"],
                    attempt_token=row["attempt_token"],
                    failure_category="rate_limited",
                )
                for _ in range(8)
            )
        )
        won = [o for o in outcomes if o is not None]
        assert len(won) == 1
        assert won[0]["attempt"] == 2

        current = await store.get_by_correlation_id(str(row["correlation_id"]))
        assert current is not None and current["attempt"] == 2

    async def test_the_attempt_budget_is_the_ceiling(self) -> None:
        store = await _live_store()
        row = await _claim(store)

        second = await store.advance_retryable_attempt(
            row["invocation_id"],
            attempt_token=row["attempt_token"],
            failure_category="provider_timeout",
        )
        assert second is not None and second["attempt"] == 2
        third = await store.advance_retryable_attempt(
            second["invocation_id"],
            attempt_token=second["attempt_token"],
            failure_category="provider_timeout",
        )
        assert third is not None and third["attempt"] == 3
        fourth = await store.advance_retryable_attempt(
            third["invocation_id"],
            attempt_token=third["attempt_token"],
            failure_category="provider_timeout",
        )
        assert fourth is None, "there is no fourth attempt"

    async def test_a_terminal_invocation_cannot_be_restarted(self) -> None:
        from datetime import datetime, timezone

        store = await _live_store()
        row = await _claim(store)
        completed = await store.complete_invocation(
            row["invocation_id"],
            attempt_token=row["attempt_token"],
            terminal={
                "status": "failed",
                "failure_category": "malformed_output",
                "failure_reason": "not json",
                "completed_at": datetime.now(timezone.utc),
            },
        )
        assert completed is not None and completed["status"] == "failed"

        restarted = await store.advance_retryable_attempt(
            row["invocation_id"],
            attempt_token=completed["attempt_token"],
            failure_category="provider_timeout",
        )
        assert restarted is None

    async def test_a_deterministic_category_is_refused_by_the_primitive(self) -> None:
        store = await _live_store()
        row = await _claim(store)
        for category in ("malformed_output", "content_safety_rejected", "budget_exceeded"):
            assert (
                await store.advance_retryable_attempt(
                    row["invocation_id"],
                    attempt_token=row["attempt_token"],
                    failure_category=category,
                )
                is None
            )
        current = await store.get_by_correlation_id(str(row["correlation_id"]))
        assert current is not None and current["attempt"] == 1


class TestDatabaseWideRetryInvariants:
    async def test_no_invocation_records_an_impossible_attempt(self) -> None:
        """Whole-table, so a row written by any code path in the suite is covered, not just these."""
        import asyncpg

        try:
            conn = await asyncpg.connect(dsn=_dsn(), timeout=5)
        except Exception:
            pytest.skip("no reachable PostgreSQL; skipping database-wide retry invariants")
        try:
            checks = {
                "an attempt below 1": "SELECT count(*) FROM reasoning_invocations WHERE attempt < 1",
                "an attempt above the 3-attempt budget": (
                    "SELECT count(*) FROM reasoning_invocations WHERE attempt > 3"
                ),
                "a started row carrying an outcome": (
                    "SELECT count(*) FROM reasoning_invocations WHERE status = 'started' "
                    "AND (failure_category IS NOT NULL OR failure_reason IS NOT NULL "
                    "     OR completed_at IS NOT NULL)"
                ),
                "a started row with no owner or no lease": (
                    "SELECT count(*) FROM reasoning_invocations WHERE status = 'started' "
                    "AND (attempt_token IS NULL OR lease_expires_at IS NULL)"
                ),
            }
            for description, sql in checks.items():
                assert await conn.fetchval(sql) == 0, description
        finally:
            await conn.close()
