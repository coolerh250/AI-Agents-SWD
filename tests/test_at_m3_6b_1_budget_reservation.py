"""Step AT-M3.6B.1 remediation -- a provider call is claimed against the budget before it is made.

AT-M3.6B.1 Independent Validation 1 found this sequence: the call lands, ``record_usage`` fails, the
failure is swallowed, and the day and month totals understate that charge permanently -- so a later
pre-flight authorizes spend the account cannot afford. No amount of error handling around the usage
write repairs it, because the failure it would have to survive is its own. Ordering does: claim the
budget FIRST, and the worst a settlement failure can do is leave the charge at the conservative
estimate that gated it.

The invariant these tests exist to establish, in one line:

    NO PROVIDER-SHAPED CALL WITHOUT A DURABLE RESERVATION, AND NO RESERVATION COUNTED TWICE.

Split deliberately in two halves. The first drives the adapter through in-process fakes and asserts
the ORDERING and the failure behaviour -- what is reserved, when, and what survives which failure.
The second runs against a real PostgreSQL and asserts what only a database can: that the identity is
unique under concurrency, that the day and month totals include unsettled reservations, that
settlement replaces rather than adds, and that migration 045 goes up, comes down, and refuses to
come down over evidence.

No network. The AT-M3.6B.1 guard fails this module if anything opens a non-loopback socket.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest

from shared.sdk.agent_reasoning.anthropic_provider import AnthropicReasoningProvider
from shared.sdk.agent_reasoning.live_config import (
    MAX_COST_PER_CALL_USD,
    MAX_COST_PER_INVOCATION_USD,
)
from shared.sdk.agent_reasoning.models import ProposalArtifact, ReasoningRequest
from shared.sdk.agent_reasoning.provider import AttemptContext, LiveProviderError
from shared.sdk.agent_reasoning.service import ReasoningService
from shared.sdk.llm_budget.models import (
    EVENT_TYPE_RELEASED_RESERVATION,
    EVENT_TYPE_RESERVED_USAGE,
)
from shared.sdk.llm_budget.store import BudgetPolicyStore
from tests.agent_reasoning_fakes import InMemoryReasoningInvocationStore
from tests.at_m3_6b_1_fakes import (
    FakeBudgetEvaluator,
    FakeSecretProvider,
    SequencedTransport,
    anthropic_body,
    live_config,
    returning_artifact,
    returning_text,
    transient_then_artifact,
    valid_artifact_json,
)

pytestmark = pytest.mark.asyncio

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
FORWARD = MIGRATIONS / "045_at_m3_6b_1_budget_reservation.sql"
DOWN = MIGRATIONS / "045_at_m3_6b_1_budget_reservation_down.sql"

_RATE_LIMITED = (429, {"type": "error", "error": {"type": "rate_limit_error"}})


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


def _adapter(
    transport: Any,
    *,
    evaluator: Any | None = None,
    secrets: Any | None = None,
    attempt: AttemptContext | None = None,
) -> AnthropicReasoningProvider:
    return AnthropicReasoningProvider(
        config=live_config(),
        secret_provider=secrets if secrets is not None else FakeSecretProvider(),
        budget_evaluator=evaluator if evaluator is not None else FakeBudgetEvaluator(),
        transport=transport,
        attempt=attempt,
    )


# --- ordering ----------------------------------------------------------------------------------


class TestReservationOrdering:
    async def test_the_reservation_is_written_before_the_credential_is_read(self) -> None:
        """Order matters twice over: nothing is spent before it is claimed, and nothing touches a
        secret backend to discover it cannot afford the call."""
        events: list[str] = []

        class _Ordered(FakeBudgetEvaluator):
            async def reserve(self, **kwargs: Any) -> Any:
                events.append("reserve")
                return await super().reserve(**kwargs)

            async def settle(self, **kwargs: Any) -> Any:
                events.append("settle")
                return await super().settle(**kwargs)

        class _Watching(FakeSecretProvider):
            def get_secret(self, name: str) -> Any:
                events.append("secret")
                return super().get_secret(name)

        class _Recording(SequencedTransport):
            async def handle_async_request(self, request: Any) -> Any:
                events.append("wire")
                return await super().handle_async_request(request)

        wire = _Recording([(200, anthropic_body(valid_artifact_json("propose")))])
        await _adapter(wire, evaluator=_Ordered(), secrets=_Watching()).propose(_request())
        assert events == ["reserve", "secret", "wire", "settle"]

    async def test_a_reservation_that_cannot_be_persisted_makes_zero_provider_calls(self) -> None:
        """The mandatory one. A budget authority that cannot confirm affordability is a refusal."""

        class _BrokenReservation(FakeBudgetEvaluator):
            async def reserve(self, **kwargs: Any) -> Any:
                raise RuntimeError("ledger unavailable")

        transport = returning_artifact("propose")
        with pytest.raises(LiveProviderError) as caught:
            await _adapter(transport, evaluator=_BrokenReservation()).propose(_request())
        assert caught.value.failure_category == "budget_exceeded"
        assert transport.call_count == 0

    async def test_a_reservation_failure_is_terminal_and_never_retried(self) -> None:
        """`budget_exceeded` is deliberately not in the retryable set: re-asking a ledger that just
        failed is not a reason to spend money."""

        class _BrokenReservation(FakeBudgetEvaluator):
            async def reserve(self, **kwargs: Any) -> Any:
                raise RuntimeError("ledger unavailable")

        store = InMemoryReasoningInvocationStore()
        transport = returning_artifact("propose")
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport, evaluator=_BrokenReservation())
        )
        assert result.invocation["failure_category"] == "budget_exceeded"
        assert result.invocation["attempt"] == 1
        assert transport.call_count == 0

    async def test_the_reserved_amount_is_the_estimate_the_preflight_gated_on(self) -> None:
        evaluator = FakeBudgetEvaluator()
        result = await _adapter(returning_artifact("propose"), evaluator=evaluator).propose(
            _request()
        )
        assert result.usage is not None
        reserved = evaluator.reservations[result.usage.reservation_key]
        assert reserved["reserved_cost_usd"] == pytest.approx(
            evaluator.preflights[0]["estimated_cost_usd"]
        )
        assert reserved["reserved_cost_usd"] <= MAX_COST_PER_CALL_USD


class TestReservationIdentity:
    async def test_the_service_reserves_against_the_invocation_and_attempt(self) -> None:
        """The canonical identity, and never the attempt_token -- which rotates and is secret."""
        store = InMemoryReasoningInvocationStore()
        evaluator = FakeBudgetEvaluator()
        transport = transient_then_artifact("propose", "timeout")
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport, evaluator=evaluator)
        )
        invocation_id = str(result.invocation["invocation_id"])
        assert set(evaluator.reservations) == {f"{invocation_id}:1", f"{invocation_id}:2"}
        tokens = {str(result.invocation["attempt_token"])}
        for key in evaluator.reservations:
            assert not any(token in key for token in tokens)

    async def test_a_repeated_reservation_of_one_attempt_charges_once(self) -> None:
        evaluator = FakeBudgetEvaluator()
        ctx = AttemptContext(invocation_id=str(uuid.uuid4()), attempt=1)
        first = await evaluator.reserve(
            reservation_key=ctx.reservation_key,
            provider="anthropic",
            model_name="claude-sonnet-5",
            estimated_prompt_tokens=1000,
            estimated_completion_tokens=1500,
            estimated_cost_usd=0.017,
        )
        second = await evaluator.reserve(
            reservation_key=ctx.reservation_key,
            provider="anthropic",
            model_name="claude-sonnet-5",
            estimated_prompt_tokens=1000,
            estimated_completion_tokens=1500,
            estimated_cost_usd=0.017,
        )
        assert first is second
        assert len(evaluator.reservations) == 1
        assert evaluator.counted_usd() == pytest.approx(0.017)

    async def test_an_unbound_direct_call_still_reserves_exactly_once(self) -> None:
        """A verb called outside the service has no durable attempt to be idempotent about, so it
        gets a fresh key -- which still leaves every provider-shaped call reserved exactly once."""
        evaluator = FakeBudgetEvaluator()
        adapter = _adapter(returning_artifact("propose"), evaluator=evaluator)
        await adapter.propose(_request())
        await adapter.propose(_request())
        assert len(evaluator.reservations) == 2
        assert all(key.startswith("unbound:") for key in evaluator.reservations)


class TestSettlement:
    async def test_a_successful_call_settles_the_reservation_to_actual_usage(self) -> None:
        evaluator = FakeBudgetEvaluator()
        result = await _adapter(
            returning_artifact("propose", input_tokens=1200, output_tokens=800),
            evaluator=evaluator,
        ).propose(_request())
        assert result.usage is not None and result.usage.settled is True
        entry = evaluator.reservations[result.usage.reservation_key]
        assert entry["state"] == "settled"
        assert entry["prompt_tokens"] == 1200 and entry["completion_tokens"] == 800
        # Counted at the actual, not at reservation + actual.
        assert evaluator.counted_usd() == pytest.approx(entry["actual_cost_usd"])

    async def test_settling_the_same_attempt_twice_does_not_charge_twice(self) -> None:
        evaluator = FakeBudgetEvaluator()
        key = f"{uuid.uuid4()}:1"
        await evaluator.reserve(
            reservation_key=key,
            provider="anthropic",
            model_name="claude-sonnet-5",
            estimated_prompt_tokens=1000,
            estimated_completion_tokens=1500,
            estimated_cost_usd=0.017,
        )
        for _ in range(3):
            await evaluator.settle(
                reservation_key=key,
                provider="anthropic",
                model_name="claude-sonnet-5",
                prompt_tokens=400,
                completion_tokens=100,
            )
        entry = evaluator.reservations[key]
        assert entry["state"] == "settled"
        assert evaluator.counted_usd() == pytest.approx(entry["actual_cost_usd"])

    async def test_a_settlement_failure_leaves_the_reservation_counted(self) -> None:
        """The defect, inverted. The charge stays visible to every later pre-flight."""

        class _BrokenSettlement(FakeBudgetEvaluator):
            async def settle(self, **kwargs: Any) -> Any:
                raise RuntimeError("ledger unavailable")

        evaluator = _BrokenSettlement()
        result = await _adapter(returning_artifact("propose"), evaluator=evaluator).propose(
            _request()
        )
        assert isinstance(result.artifact, ProposalArtifact)
        assert result.usage is not None and result.usage.settled is False
        assert evaluator.reservations[result.usage.reservation_key]["state"] == "reserved"
        assert evaluator.counted_usd() == pytest.approx(result.usage.reserved_cost_usd)
        assert evaluator.counted_usd() > 0

    async def test_a_settlement_failure_is_visible_in_the_invocation_audit(self) -> None:
        """Truthful metadata, not a claim of actual-cost precision the ledger does not have."""

        class _BrokenSettlement(FakeBudgetEvaluator):
            async def settle(self, **kwargs: Any) -> Any:
                raise RuntimeError("ledger unavailable")

        written: list[dict[str, Any]] = []

        class _Audit:
            def build_audit_event(self, **kwargs: Any) -> dict[str, Any]:
                return kwargs

            async def write_audit_event(self, event: dict[str, Any]) -> str:
                written.append(event)
                return "audit-ref"

        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store, audit_client=_Audit())
        await service.invoke(
            _request(),
            provider=_adapter(returning_artifact("propose"), evaluator=_BrokenSettlement()),
        )
        terminal = [e for e in written if e["decision_type"] == "reasoning_invoked"]
        assert len(terminal) == 1
        refs = terminal[0]["artifact_refs"]
        assert refs["usage_settlement_pending"] is True
        assert refs["budget_reservation_key"] is not None
        assert refs["budget_reserved_cost_usd"] > 0

    async def test_a_later_settlement_of_the_same_attempt_succeeds_and_replaces(self) -> None:
        """Retrying the settlement is safe, because the reservation is still there to settle."""

        class _FailsOnce(FakeBudgetEvaluator):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self.failed = False

            async def settle(self, **kwargs: Any) -> Any:
                if not self.failed:
                    self.failed = True
                    raise RuntimeError("ledger unavailable")
                return await super().settle(**kwargs)

        evaluator = _FailsOnce()
        result = await _adapter(returning_artifact("propose"), evaluator=evaluator).propose(
            _request()
        )
        key = result.usage.reservation_key  # type: ignore[union-attr]
        reserved_total = evaluator.counted_usd()
        await evaluator.settle(
            reservation_key=key,
            provider="anthropic",
            model_name="claude-sonnet-5",
            prompt_tokens=400,
            completion_tokens=300,
        )
        entry = evaluator.reservations[key]
        assert entry["state"] == "settled"
        assert evaluator.counted_usd() == pytest.approx(entry["actual_cost_usd"])
        assert reserved_total > 0


class TestPaidButUnusable:
    @pytest.mark.parametrize(
        "body,category",
        [
            ("{not json", "malformed_output"),
            ({"summary": "s", "rationale_summary": "r", "confidence": 2.5}, "malformed_output"),
        ],
        ids=["unparseable", "schema-invalid"],
    )
    async def test_a_rejected_artifact_is_still_accounted(self, body: Any, category: str) -> None:
        evaluator = FakeBudgetEvaluator()
        transport = (
            returning_text(body, input_tokens=500, output_tokens=200)
            if isinstance(body, str)
            else SequencedTransport(
                [(200, anthropic_body(body, input_tokens=500, output_tokens=200))]
            )
        )
        with pytest.raises(LiveProviderError) as caught:
            await _adapter(transport, evaluator=evaluator).propose(_request())
        assert caught.value.failure_category == category
        assert caught.value.usage is not None
        assert caught.value.usage.reservation_key is not None
        assert evaluator.counted_usd() > 0

    async def test_a_timeout_retains_its_reservation(self) -> None:
        """A timeout cannot prove no request arrived, so nothing is given back on the guess."""
        evaluator = FakeBudgetEvaluator()
        with pytest.raises(LiveProviderError) as caught:
            await _adapter(SequencedTransport(["timeout"]), evaluator=evaluator).propose(_request())
        assert caught.value.failure_category == "provider_timeout"
        assert caught.value.usage is not None
        key = caught.value.usage.reservation_key
        assert key is not None
        assert evaluator.reservations[key]["state"] == "reserved"
        assert evaluator.releases == []
        assert evaluator.counted_usd() > 0

    async def test_a_missing_credential_releases_because_absence_is_provable(self) -> None:
        """The one release path: no client was built, so no request can have left."""
        evaluator = FakeBudgetEvaluator()
        transport = returning_artifact("propose")
        with pytest.raises(LiveProviderError) as caught:
            await _adapter(
                transport, evaluator=evaluator, secrets=FakeSecretProvider(present=False)
            ).propose(_request())
        assert caught.value.failure_category == "provider_unauthorized"
        assert transport.call_count == 0
        assert len(evaluator.releases) == 1
        assert evaluator.counted_usd() == pytest.approx(0.0)


class TestZombieAndRetryAccounting:
    async def test_both_attempts_of_a_retry_are_counted(self) -> None:
        store = InMemoryReasoningInvocationStore()
        evaluator = FakeBudgetEvaluator()
        transport = transient_then_artifact("propose", "timeout")
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport, evaluator=evaluator)
        )
        assert result.invocation["attempt"] == 2
        assert len(evaluator.reservations) == 2
        states = sorted(e["state"] for e in evaluator.reservations.values())
        # Attempt 1 timed out and keeps its conservative reservation; attempt 2 settled to actual.
        assert states == ["reserved", "settled"]
        assert evaluator.counted_usd() > 0

    async def test_a_superseded_zombie_attempt_still_counts(self) -> None:
        """Its artifact is discarded because only one can be canonical; its charge is not."""
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        request = _request()
        evaluator = FakeBudgetEvaluator()

        from tests.at_m3_6b_1_fakes import GatedTransport

        gated = GatedTransport()
        slow = _adapter(gated, evaluator=evaluator)
        first = asyncio.create_task(service.invoke(request, provider=slow))
        await gated.arrived.wait()

        store.expire_lease(str(request.correlation_id))
        second = await service.invoke(
            request, provider=_adapter(returning_artifact("propose"), evaluator=evaluator)
        )
        gated.release()
        zombie = await first

        assert second.invocation["attempt"] == 2
        assert zombie.invocation["attempt"] == 2, "the zombie is handed the canonical row"
        # Two attempts really called a provider, so two reservations exist and both are counted.
        assert len(evaluator.reservations) == 2
        assert evaluator.counted_usd() > 0

    async def test_a_replay_creates_no_reservation_and_no_new_spend(self) -> None:
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        request = _request()
        evaluator = FakeBudgetEvaluator()
        adapter = _adapter(returning_artifact("propose"), evaluator=evaluator)

        await service.invoke(request, provider=adapter)
        before = evaluator.counted_usd()
        replay = await service.invoke(request, provider=adapter)

        assert replay.disposition == "replay"
        assert len(evaluator.reservations) == 1
        assert evaluator.counted_usd() == pytest.approx(before)

    async def test_a_terminal_failure_replay_creates_no_reservation(self) -> None:
        store = InMemoryReasoningInvocationStore()
        service = ReasoningService(store=store)
        request = _request()
        evaluator = FakeBudgetEvaluator()
        adapter = _adapter(
            SequencedTransport([(200, anthropic_body("{not json"))]), evaluator=evaluator
        )

        await service.invoke(request, provider=adapter)
        before = evaluator.counted_usd()
        replay = await service.invoke(request, provider=adapter)

        assert replay.disposition == "replay"
        assert replay.invocation["status"] == "failed"
        assert len(evaluator.reservations) == 1
        assert evaluator.counted_usd() == pytest.approx(before)


class TestCostEnvelope:
    async def test_three_exhausted_attempts_stay_inside_the_authorized_envelope(self) -> None:
        store = InMemoryReasoningInvocationStore()
        evaluator = FakeBudgetEvaluator()
        transport = SequencedTransport(["timeout", _RATE_LIMITED, "timeout"])
        result = await ReasoningService(store=store).invoke(
            _request(), provider=_adapter(transport, evaluator=evaluator)
        )
        assert result.invocation["status"] == "failed"
        assert transport.call_count == 3
        assert len(evaluator.reservations) == 3, "one reservation per provider-shaped call"
        total = evaluator.counted_usd()
        assert total <= MAX_COST_PER_INVOCATION_USD
        assert all(
            e["reserved_cost_usd"] <= MAX_COST_PER_CALL_USD for e in evaluator.reservations.values()
        )

    async def test_the_envelope_is_the_per_call_cap_times_the_attempt_budget(self) -> None:
        """Not a fourth independent number that could drift out of step with the other two."""
        assert MAX_COST_PER_INVOCATION_USD == pytest.approx(MAX_COST_PER_CALL_USD * 3)


# --- against a real PostgreSQL ------------------------------------------------------------------


def _base_dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")


def _with_database(dsn: str, database: str) -> str:
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _ordered_migrations() -> list[Path]:
    return sorted(
        (
            p
            for p in MIGRATIONS.glob("*.sql")
            if p.name[:3].isdigit() and not p.name.endswith("_down.sql")
        ),
        key=lambda p: int(p.name[:3]),
    )


class _ThrowawayDatabase:
    """Its own database per test, migrated from 001. Reversing a migration on a shared database
    would destroy every other test's data and make the result depend on ordering."""

    def __init__(self) -> None:
        self.name = f"m36b1_res_{uuid.uuid4().hex[:12]}"
        self.dsn = _with_database(_base_dsn(), self.name)

    async def __aenter__(self) -> "_ThrowawayDatabase":
        try:
            admin = await asyncpg.connect(dsn=_base_dsn(), timeout=5)
        except Exception:
            pytest.skip("no reachable PostgreSQL; skipping migration 045 test")
        try:
            await admin.execute(f'CREATE DATABASE "{self.name}"')
        finally:
            await admin.close()
        return self

    async def __aexit__(self, *_: object) -> None:
        admin = await asyncpg.connect(dsn=_base_dsn(), timeout=5)
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1",
                self.name,
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{self.name}"')
        finally:
            await admin.close()

    async def apply_through(self, last: int) -> None:
        conn = await asyncpg.connect(dsn=self.dsn, timeout=10)
        try:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            for path in _ordered_migrations():
                if int(path.name[:3]) > last:
                    continue
                await conn.execute(path.read_text(encoding="utf-8"))
        finally:
            await conn.close()

    async def run(self, path: Path) -> None:
        conn = await asyncpg.connect(dsn=self.dsn, timeout=10)
        try:
            await conn.execute(path.read_text(encoding="utf-8"))
        finally:
            await conn.close()

    async def connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=10)


class TestMigration045:
    async def test_045_is_the_next_number_after_044(self) -> None:
        """Derived from repository truth. AT-M3.6B.1 shipped 044, so the remediation's is 045.

        Asserted the narrowed way for the reason AT-D23 section 7 and AT-D24 both record: a stage
        claiming its own migration is the last that will ever exist forbids every later authorized
        one. This slice tripped that assertion twice already; it does not write a third.
        """
        numbers = [int(p.name[:3]) for p in _ordered_migrations()]
        assert 45 in numbers
        assert numbers.count(45) == 1
        assert max(n for n in numbers if n < 45) == 44
        assert FORWARD.exists() and DOWN.exists()

    async def test_no_migration_below_045_is_touched(self) -> None:
        """Everything this branch changed under migrations/ is numbered 044 or 045, and nothing
        below it. A migration that edits history is how a schema and its evidence stop agreeing."""
        import subprocess

        def _git(*args: str) -> list[str] | None:
            done = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
            if done.returncode != 0:  # pragma: no cover - only when git is unavailable
                return None
            return [line.strip() for line in done.stdout.splitlines() if line.strip()]

        tracked = _git("diff", "--name-only", "e50d422", "--", "migrations/")
        untracked = _git("ls-files", "--others", "--exclude-standard", "--", "migrations/")
        if tracked is None or untracked is None:
            pytest.skip("git unavailable")
        touched = set(tracked) | set(untracked)
        numbers = {int(name.rsplit("/", 1)[-1][:3]) for name in touched}
        assert numbers == {44, 45}, sorted(touched)

    async def test_forward_adds_the_identity_and_the_vocabulary(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            conn = await db.connect()
            try:
                column = await conn.fetchval(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name='llm_budget_events' AND column_name='reservation_key'"
                )
                assert column == "text"
                clause = await conn.fetchval(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname='chk_llm_budget_events_event_type'"
                )
                for event_type in ("reserved_usage", "released_reservation"):
                    assert event_type in clause
                # And the four Stage 35 types are all still permitted.
                for event_type in (
                    "preflight",
                    "recorded_usage",
                    "budget_exceeded",
                    "budget_warning",
                ):
                    assert event_type in clause
                index = await conn.fetchval(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE indexname='uq_llm_budget_events_reservation_key'"
                )
                assert "UNIQUE" in index and "reservation_key IS NOT NULL" in index
            finally:
                await conn.close()

    async def test_one_attempt_cannot_hold_two_reservations(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            conn = await db.connect()
            try:
                await conn.execute(
                    "INSERT INTO llm_budget_events "
                    "(provider, model_name, event_type, decision, estimated_cost_usd, "
                    " reservation_key) VALUES ($1,$2,$3,$4,$5,$6)",
                    "anthropic",
                    "claude-sonnet-5",
                    "reserved_usage",
                    "allowed",
                    0.02,
                    "inv-1:1",
                )
                with pytest.raises(asyncpg.UniqueViolationError):
                    await conn.execute(
                        "INSERT INTO llm_budget_events "
                        "(provider, model_name, event_type, decision, estimated_cost_usd, "
                        " reservation_key) VALUES ($1,$2,$3,$4,$5,$6)",
                        "anthropic",
                        "claude-sonnet-5",
                        "reserved_usage",
                        "allowed",
                        0.02,
                        "inv-1:1",
                    )
                # NULLs do not collide -- every historical row carries one.
                for _ in range(3):
                    await conn.execute(
                        "INSERT INTO llm_budget_events "
                        "(provider, model_name, event_type, decision) VALUES ($1,$2,$3,$4)",
                        "mock",
                        "mock-model",
                        "preflight",
                        "allowed",
                    )
            finally:
                await conn.close()

    async def test_a_reservation_must_name_an_attempt(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            conn = await db.connect()
            try:
                with pytest.raises(asyncpg.CheckViolationError):
                    await conn.execute(
                        "INSERT INTO llm_budget_events "
                        "(provider, model_name, event_type, decision) VALUES ($1,$2,$3,$4)",
                        "anthropic",
                        "claude-sonnet-5",
                        "reserved_usage",
                        "allowed",
                    )
            finally:
                await conn.close()

    async def test_up_down_up_up(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            await db.run(DOWN)
            conn = await db.connect()
            try:
                assert (
                    await conn.fetchval(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_name='llm_budget_events' AND column_name='reservation_key'"
                    )
                    == 0
                )
                clause = await conn.fetchval(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname='chk_llm_budget_events_event_type'"
                )
                assert "reserved_usage" not in clause
            finally:
                await conn.close()
            await db.run(FORWARD)
            await db.run(FORWARD)  # idempotent
            conn = await db.connect()
            try:
                assert (
                    await conn.fetchval(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_name='llm_budget_events' AND column_name='reservation_key'"
                    )
                    == 1
                )
            finally:
                await conn.close()

    async def test_the_reverse_migration_fails_closed_over_reservation_evidence(self) -> None:
        """Rolling back would drop an unsettled claim on money that may already be spent."""
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            conn = await db.connect()
            try:
                await conn.execute(
                    "INSERT INTO llm_budget_events "
                    "(provider, model_name, event_type, decision, estimated_cost_usd, "
                    " reservation_key) VALUES ($1,$2,$3,$4,$5,$6)",
                    "anthropic",
                    "claude-sonnet-5",
                    "reserved_usage",
                    "allowed",
                    0.02,
                    "inv-guard:1",
                )
            finally:
                await conn.close()

            with pytest.raises(asyncpg.RestrictViolationError):
                await db.run(DOWN)

            conn = await db.connect()
            try:
                # The evidence and the widened vocabulary both survive the refusal.
                assert (
                    await conn.fetchval(
                        "SELECT count(*) FROM llm_budget_events WHERE reservation_key='inv-guard:1'"
                    )
                    == 1
                )
                clause = await conn.fetchval(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname='chk_llm_budget_events_event_type'"
                )
                assert "reserved_usage" in clause
            finally:
                await conn.close()


class TestDurableAccounting:
    """The half only a database can answer: what the day and the month actually count."""

    async def _store(self, db: _ThrowawayDatabase) -> BudgetPolicyStore:
        return BudgetPolicyStore(db.dsn)

    async def test_an_unsettled_reservation_counts_toward_the_day_and_the_month(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            store = await self._store(db)
            assert await store.get_daily_usage_usd(provider="anthropic") == pytest.approx(0.0)

            await store.reserve_attempt_cost(
                reservation_key="inv-a:1",
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_prompt_tokens=1000,
                estimated_completion_tokens=1500,
                estimated_cost_usd=0.25,
            )
            assert await store.get_daily_usage_usd(provider="anthropic") == pytest.approx(0.25)
            assert await store.get_monthly_usage_usd(provider="anthropic") == pytest.approx(0.25)

    async def test_settlement_replaces_the_reservation_rather_than_adding_to_it(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            store = await self._store(db)
            await store.reserve_attempt_cost(
                reservation_key="inv-b:1",
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_prompt_tokens=1000,
                estimated_completion_tokens=1500,
                estimated_cost_usd=0.25,
            )
            settled = await store.settle_attempt_cost(
                reservation_key="inv-b:1",
                actual_prompt_tokens=400,
                actual_completion_tokens=200,
                actual_cost_usd=0.0028,
            )
            assert settled is not None and settled.event_type == "recorded_usage"
            assert await store.get_daily_usage_usd(provider="anthropic") == pytest.approx(0.0028)
            # ONE row for the attempt, from reservation through settlement.
            conn = await db.connect()
            try:
                assert (
                    await conn.fetchval(
                        "SELECT count(*) FROM llm_budget_events WHERE reservation_key='inv-b:1'"
                    )
                    == 1
                )
            finally:
                await conn.close()

    async def test_settling_twice_does_not_charge_twice(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            store = await self._store(db)
            await store.reserve_attempt_cost(
                reservation_key="inv-c:1",
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_cost_usd=0.25,
            )
            for _ in range(3):
                await store.settle_attempt_cost(
                    reservation_key="inv-c:1",
                    actual_prompt_tokens=400,
                    actual_completion_tokens=200,
                    actual_cost_usd=0.0028,
                )
            assert await store.get_daily_usage_usd(provider="anthropic") == pytest.approx(0.0028)

    async def test_eight_racers_reserve_one_attempt_exactly_once(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            store = await self._store(db)
            rows = await asyncio.gather(
                *(
                    store.reserve_attempt_cost(
                        reservation_key="inv-d:1",
                        provider="anthropic",
                        model_name="claude-sonnet-5",
                        estimated_cost_usd=0.25,
                    )
                    for _ in range(8)
                )
            )
            assert len({r.budget_event_id for r in rows}) == 1
            assert await store.get_daily_usage_usd(provider="anthropic") == pytest.approx(0.25)

    async def test_a_released_reservation_stops_counting_but_stays_on_record(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            store = await self._store(db)
            await store.reserve_attempt_cost(
                reservation_key="inv-e:1",
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_cost_usd=0.25,
            )
            released = await store.release_attempt_reservation(
                reservation_key="inv-e:1", reason="credential_unavailable_before_any_request"
            )
            assert released is not None
            assert released.event_type == EVENT_TYPE_RELEASED_RESERVATION
            assert await store.get_daily_usage_usd(provider="anthropic") == pytest.approx(0.0)
            assert await store.get_reservation(reservation_key="inv-e:1") is not None

    async def test_a_release_cannot_undo_a_settlement(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            store = await self._store(db)
            await store.reserve_attempt_cost(
                reservation_key="inv-f:1",
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_cost_usd=0.25,
            )
            await store.settle_attempt_cost(
                reservation_key="inv-f:1",
                actual_prompt_tokens=400,
                actual_completion_tokens=200,
                actual_cost_usd=0.0028,
            )
            assert await store.release_attempt_reservation(reservation_key="inv-f:1") is None, (
                "a settled charge is not releasable"
            )
            assert await store.get_daily_usage_usd(provider="anthropic") == pytest.approx(0.0028)

    async def test_a_preflight_sees_a_reservation_it_has_not_yet_settled(self) -> None:
        """The point of the whole exercise: an unsettled charge still gates the next call."""
        from shared.sdk.llm_budget.policy import BudgetPolicyEvaluator

        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            store = await self._store(db)
            await store.create_policy(
                policy_name="at-m3.6b.1-remediation",
                provider="anthropic",
                scope_type="provider",
                max_cost_per_day_usd=0.30,
                max_cost_per_month_usd=5.0,
            )
            evaluator = BudgetPolicyEvaluator(store=store)

            first = await evaluator.preflight(
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_prompt_tokens=1000,
                estimated_completion_tokens=1500,
            )
            assert first.decision == "allowed"

            # Claim most of the day's budget and never settle it -- the failure mode Independent
            # Validation 1 found. The next pre-flight must still see it.
            await store.reserve_attempt_cost(
                reservation_key="inv-g:1",
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_cost_usd=0.29,
            )
            second = await evaluator.preflight(
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_prompt_tokens=1000,
                estimated_completion_tokens=1500,
            )
            assert second.decision == "blocked"
            assert second.cap_breached == "cost_per_day"

    async def test_the_total_survives_a_restart(self) -> None:
        """A fresh store object, a fresh connection: the truth is in the database, not in memory."""
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            await (await self._store(db)).reserve_attempt_cost(
                reservation_key="inv-h:1",
                provider="anthropic",
                model_name="claude-sonnet-5",
                estimated_cost_usd=0.25,
            )
            reborn = BudgetPolicyStore(db.dsn)
            assert await reborn.get_daily_usage_usd(provider="anthropic") == pytest.approx(0.25)

    async def test_a_provider_call_with_no_reservation_is_representable_nowhere(self) -> None:
        """Database-wide: every reservation-shaped ledger row names exactly one attempt."""
        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            store = await self._store(db)
            for index in range(3):
                await store.reserve_attempt_cost(
                    reservation_key=f"inv-i:{index + 1}",
                    provider="anthropic",
                    model_name="claude-sonnet-5",
                    estimated_cost_usd=0.25,
                )
            conn = await db.connect()
            try:
                orphaned = await conn.fetchval(
                    "SELECT count(*) FROM llm_budget_events "
                    "WHERE event_type = ANY($1::text[]) AND reservation_key IS NULL",
                    [EVENT_TYPE_RESERVED_USAGE, EVENT_TYPE_RELEASED_RESERVATION],
                )
                assert orphaned == 0
                duplicated = await conn.fetchval(
                    "SELECT count(*) FROM (SELECT reservation_key FROM llm_budget_events "
                    "WHERE reservation_key IS NOT NULL GROUP BY reservation_key "
                    "HAVING count(*) > 1) d"
                )
                assert duplicated == 0
            finally:
                await conn.close()


class TestLiveShapedReservationOnRealPostgres:
    """One end-to-end pass: service, adapter, fake transport, real reasoning store, real ledger."""

    async def test_a_retried_invocation_leaves_one_reservation_per_attempt(self) -> None:
        from shared.sdk.agent_reasoning.store import ReasoningInvocationStore
        from shared.sdk.llm_budget.policy import BudgetPolicyEvaluator

        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            budget_store = BudgetPolicyStore(db.dsn)
            await budget_store.create_policy(
                policy_name="at-m3.6b.1-remediation-e2e",
                provider="anthropic",
                scope_type="provider",
                max_cost_per_day_usd=5.0,
                max_cost_per_month_usd=50.0,
            )
            evaluator = BudgetPolicyEvaluator(store=budget_store)
            transport = transient_then_artifact("propose", "timeout", _RATE_LIMITED)
            adapter = AnthropicReasoningProvider(
                config=live_config(),
                secret_provider=FakeSecretProvider(),
                budget_evaluator=evaluator,
                budget_store=budget_store,
                transport=transport,
            )
            service = ReasoningService(store=ReasoningInvocationStore(db.dsn))
            result = await service.invoke(_request(), provider=adapter)

            assert isinstance(result.artifact, ProposalArtifact)
            assert result.invocation["attempt"] == 3
            assert transport.call_count == 3

            invocation_id = str(result.invocation["invocation_id"])
            conn = await db.connect()
            try:
                keys = [
                    r["reservation_key"]
                    for r in await conn.fetch(
                        "SELECT reservation_key FROM llm_budget_events "
                        "WHERE reservation_key IS NOT NULL ORDER BY reservation_key"
                    )
                ]
                assert keys == [f"{invocation_id}:{n}" for n in (1, 2, 3)]
                states = {
                    r["reservation_key"]: r["event_type"]
                    for r in await conn.fetch(
                        "SELECT reservation_key, event_type FROM llm_budget_events "
                        "WHERE reservation_key IS NOT NULL"
                    )
                }
                # Attempts 1 and 2 failed before any usage was known; attempt 3 settled.
                assert states[f"{invocation_id}:1"] == EVENT_TYPE_RESERVED_USAGE
                assert states[f"{invocation_id}:2"] == EVENT_TYPE_RESERVED_USAGE
                assert states[f"{invocation_id}:3"] == "recorded_usage"
            finally:
                await conn.close()

            total = await budget_store.get_daily_usage_usd(provider="anthropic")
            assert 0 < total <= MAX_COST_PER_INVOCATION_USD

    async def test_a_replay_on_real_postgres_adds_no_reservation(self) -> None:
        from shared.sdk.agent_reasoning.store import ReasoningInvocationStore
        from shared.sdk.llm_budget.policy import BudgetPolicyEvaluator

        async with _ThrowawayDatabase() as db:
            await db.apply_through(45)
            budget_store = BudgetPolicyStore(db.dsn)
            await budget_store.create_policy(
                policy_name="at-m3.6b.1-remediation-replay",
                provider="anthropic",
                scope_type="provider",
                max_cost_per_day_usd=5.0,
                max_cost_per_month_usd=50.0,
            )
            transport = returning_artifact("propose")
            adapter = AnthropicReasoningProvider(
                config=live_config(),
                secret_provider=FakeSecretProvider(),
                budget_evaluator=BudgetPolicyEvaluator(store=budget_store),
                budget_store=budget_store,
                transport=transport,
            )
            service = ReasoningService(store=ReasoningInvocationStore(db.dsn))
            request = _request()
            await service.invoke(request, provider=adapter)
            before = await budget_store.get_daily_usage_usd(provider="anthropic")
            replay = await service.invoke(request, provider=adapter)

            assert replay.disposition == "replay"
            assert transport.call_count == 1
            assert await budget_store.get_daily_usage_usd(provider="anthropic") == pytest.approx(
                before
            )
