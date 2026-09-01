"""Step AT-M3.4 (rebaselined) -- durable reasoning artifacts, leases and takeover.

AT-M3.4 Validation 2 failed on one property that AT-M3.1 never claimed and every later milestone
assumed: that a SUCCEEDED reasoning invocation could be replayed. It could not. The invocation
committed its terminal status while the artifact lived only in the calling process's memory, so a
crash in between left the correlation terminal (never re-invokable) and empty (nothing to replay).
The work was stranded permanently.

These tests are the ones that could not be written before, because there was nothing durable to
assert about. They run against real PostgreSQL because every guarantee here is a constraint, a
trigger or a compare-and-swap -- none of them provable against a fake, and two of them (the CHECK
and the terminal-immutability trigger) exist precisely to survive a caller that bypasses the
service entirely.

Where expiry is under test, the incumbent's lease is pushed into the past rather than waited out.
Sleeping through a real TTL would make the suite slow and flaky, and what is under test is the
BEHAVIOUR at expiry -- PostgreSQL's own clock still decides when that is. Shortening the TAKER's
TTL would not do: that governs the lease a taker grants, not whether the incumbent's has run out,
and confusing the two produces a test that passes for the wrong reason.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest

from shared.sdk.agent_reasoning.mock_provider import MockReasoningProvider
from shared.sdk.agent_reasoning.models import ProposalArtifact, ReasoningRequest
from shared.sdk.agent_reasoning.service import (
    ReasoningArtifactCorruptError,
    ReasoningService,
)
from shared.sdk.agent_reasoning.store import ReasoningInvocationStore

_SKIP = "no reachable PostgreSQL with migration 040 applied; skipping"


async def _store_or_skip(**kwargs) -> ReasoningInvocationStore:
    store = ReasoningInvocationStore(**kwargs)
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip(_SKIP)
    try:
        if await conn.fetchval("SELECT to_regclass('public.reasoning_invocations')") is None:
            pytest.skip(_SKIP)
        if not await conn.fetchval(
            "SELECT 1 FROM information_schema.columns WHERE table_name='reasoning_invocations' "
            "AND column_name='artifact'"
        ):
            pytest.skip(_SKIP)
    finally:
        await conn.close()
    return store


_ARTIFACT = {
    "summary": "a bounded option",
    "rationale_summary": "because it is the smallest thing that works",
    "confidence": None,
    "assumptions": [],
    "constraints": [],
    "risks": [],
    "questions": [],
    "recommendation": "do the boring thing",
}


def _begin(correlation_id: str | None = None, verb: str = "propose") -> dict:
    return {
        "project_id": None,
        "thread_id": None,
        "requested_by_principal_id": None,
        "reasoning_verb": verb,
        "requested_provider_name": "mock",
        "provider_mode": "mock",
        "model_name": None,
        "round_number": 1,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "started_at": datetime.now(timezone.utc),
    }


def _terminal(status: str = "succeeded", **overrides) -> dict:
    data = {
        "status": status,
        "failure_category": None if status == "succeeded" else "provider_unavailable",
        "failure_reason": None if status == "succeeded" else "test failure",
        "latency_ms": 3,
        "audit_ref": None,
        "completed_at": datetime.now(timezone.utc),
        "artifact_type": "ProposalArtifact" if status == "succeeded" else None,
        "artifact": dict(_ARTIFACT) if status == "succeeded" else None,
    }
    data.update(overrides)
    return data


async def _expire_lease(store: ReasoningInvocationStore, correlation_id: str) -> None:
    """Simulate the owner dying and its lease running out.

    The lease is pushed into the past ON THE DATABASE CLOCK, which is the only clock the takeover
    predicate consults. Note what is NOT done here: shortening the TAKER's configured TTL, which
    governs the lease a taker would grant and says nothing about whether the incumbent's has
    expired. Confusing the two is easy and produces a test that passes for the wrong reason.
    """
    conn = await store._connect()
    try:
        await conn.execute(
            "UPDATE reasoning_invocations SET lease_expires_at = now() - interval '1 minute' "
            "WHERE correlation_id=$1 AND status='started'",
            uuid.UUID(str(correlation_id)),
        )
    finally:
        await conn.close()


async def _as_pre_contract_row(store: ReasoningInvocationStore, invocation_id, sql: str) -> None:
    """Put a row into a shape only a pre-migration-040 write could have produced.

    The two NOT VALID constraints are dropped for the write and restored afterwards, because that
    is literally how such a row came to exist: it was written before the constraint did. Reaching
    the shape any other way would be asserting something about a database that never happened.
    """
    conn = await store._connect()
    try:
        for name in ("success_artifact", "lease"):
            await conn.execute(
                f"ALTER TABLE reasoning_invocations DROP CONSTRAINT "
                f"chk_reasoning_invocations_{name}"
            )
        await conn.execute(sql, invocation_id)
        await conn.execute(
            "ALTER TABLE reasoning_invocations ADD CONSTRAINT "
            "chk_reasoning_invocations_success_artifact CHECK ("
            "(status = 'succeeded' AND artifact_type IS NOT NULL AND artifact IS NOT NULL) "
            "OR (status <> 'succeeded' AND artifact_type IS NULL AND artifact IS NULL)) NOT VALID"
        )
        await conn.execute(
            "ALTER TABLE reasoning_invocations ADD CONSTRAINT "
            "chk_reasoning_invocations_lease CHECK ("
            "(status = 'started' AND attempt_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'started' AND lease_expires_at IS NULL)) NOT VALID"
        )
    finally:
        await conn.close()


async def _raw(store: ReasoningInvocationStore, correlation_id: str) -> dict:
    conn = await store._connect()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM reasoning_invocations WHERE correlation_id=$1",
            uuid.UUID(str(correlation_id)),
        )
        return dict(row)
    finally:
        await conn.close()


# --- the success invariant --------------------------------------------------------------------


async def test_a_succeeded_invocation_carries_its_artifact_in_the_same_write():
    store = await _store_or_skip()
    data = _begin()
    _owned, row = await store.try_begin_invocation(data)
    assert row["artifact"] is None and row["status"] == "started"

    completed = await store.complete_invocation(
        row["invocation_id"], attempt_token=row["attempt_token"], terminal=_terminal()
    )
    assert completed["status"] == "succeeded"
    assert completed["artifact"] == _ARTIFACT
    assert completed["artifact_type"] == "ProposalArtifact"
    # A terminal row owns nothing.
    assert completed["lease_expires_at"] is None


async def test_the_database_refuses_a_success_with_no_artifact():
    """The invariant, at the layer that has to hold even for a caller that skips the service.

    This is the state AT-M3.4 Validation 2 failed on, made unrepresentable rather than merely
    avoided.
    """
    store = await _store_or_skip()
    _owned, row = await store.try_begin_invocation(_begin())
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.IntegrityConstraintViolationError) as exc:
            await conn.execute(
                "UPDATE reasoning_invocations SET status='succeeded', completed_at=now(), "
                "lease_expires_at=NULL WHERE invocation_id=$1",
                row["invocation_id"],
            )
        assert "success_artifact" in str(exc.value)

        # And the mirror image: a failure may not smuggle one in.
        with pytest.raises(asyncpg.IntegrityConstraintViolationError):
            await conn.execute(
                "UPDATE reasoning_invocations SET status='failed', "
                "failure_category='provider_unavailable', completed_at=now(), "
                "lease_expires_at=NULL, artifact_type='ProposalArtifact', artifact=$2::jsonb "
                "WHERE invocation_id=$1",
                row["invocation_id"],
                json.dumps(_ARTIFACT),
            )
    finally:
        await conn.close()


async def test_the_database_refuses_an_artifact_type_that_disagrees_with_the_verb():
    store = await _store_or_skip()
    _owned, row = await store.try_begin_invocation(_begin(verb="propose"))
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.IntegrityConstraintViolationError) as exc:
            await conn.execute(
                "UPDATE reasoning_invocations SET status='succeeded', completed_at=now(), "
                "lease_expires_at=NULL, artifact_type='PlanDraftArtifact', artifact=$2::jsonb "
                "WHERE invocation_id=$1",
                row["invocation_id"],
                json.dumps(_ARTIFACT),
            )
        assert "artifact_type" in str(exc.value)
    finally:
        await conn.close()


async def test_a_scalar_is_not_an_artifact():
    store = await _store_or_skip()
    _owned, row = await store.try_begin_invocation(_begin())
    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.IntegrityConstraintViolationError):
            await conn.execute(
                "UPDATE reasoning_invocations SET status='succeeded', completed_at=now(), "
                "lease_expires_at=NULL, artifact_type='ProposalArtifact', "
                "artifact='\"just a string\"'::jsonb WHERE invocation_id=$1",
                row["invocation_id"],
            )
    finally:
        await conn.close()


# --- terminal immutability ---------------------------------------------------------------------


async def test_a_terminal_artifact_cannot_be_replaced_by_another_valid_one():
    """Service discipline is not the guarantee. A recovery copy is only worth reading if nothing
    can quietly swap it for a different, equally well-formed plan after the fact."""
    store = await _store_or_skip()
    _owned, row = await store.try_begin_invocation(_begin())
    await store.complete_invocation(
        row["invocation_id"], attempt_token=row["attempt_token"], terminal=_terminal()
    )
    replacement = dict(_ARTIFACT, summary="a completely different conclusion")

    conn = await store._connect()
    try:
        for sql, params in (
            (
                "UPDATE reasoning_invocations SET artifact=$2::jsonb WHERE invocation_id=$1",
                (row["invocation_id"], json.dumps(replacement)),
            ),
            (
                "UPDATE reasoning_invocations SET status='failed', "
                "failure_category='provider_unavailable' WHERE invocation_id=$1",
                (row["invocation_id"],),
            ),
            (
                "UPDATE reasoning_invocations SET attempt=attempt+5 WHERE invocation_id=$1",
                (row["invocation_id"],),
            ),
            (
                "UPDATE reasoning_invocations SET attempt_token=$2 WHERE invocation_id=$1",
                (row["invocation_id"], uuid.uuid4()),
            ),
            (
                "UPDATE reasoning_invocations SET provider_mode='disabled' WHERE invocation_id=$1",
                (row["invocation_id"],),
            ),
            (
                "UPDATE reasoning_invocations SET reasoning_verb='critique' WHERE invocation_id=$1",
                (row["invocation_id"],),
            ),
            (
                "UPDATE reasoning_invocations SET correlation_id=$2 WHERE invocation_id=$1",
                (row["invocation_id"], uuid.uuid4()),
            ),
        ):
            with pytest.raises(asyncpg.PostgresError):
                await conn.execute(sql, *params)
    finally:
        await conn.close()

    unchanged = await _raw(store, row["correlation_id"])
    assert json.loads(unchanged["artifact"]) == _ARTIFACT
    assert unchanged["status"] == "succeeded"


async def test_an_attempt_counter_can_never_be_rewound():
    """The attempt count is how many times a provider was actually asked. Rewinding it would make
    the record understate real provider usage."""
    store = await _store_or_skip(lease_ttl_seconds=300)
    data = _begin()
    _owned, row = await store.try_begin_invocation(data)
    await _expire_lease(store, data["correlation_id"])
    taken = await store.try_take_over_invocation(data["correlation_id"])
    assert taken["attempt"] == 2

    conn = await store._connect()
    try:
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                "UPDATE reasoning_invocations SET attempt=1 WHERE invocation_id=$1",
                row["invocation_id"],
            )
    finally:
        await conn.close()


# --- the lease ---------------------------------------------------------------------------------


async def test_a_claim_is_leased_on_the_database_clock():
    store = await _store_or_skip(lease_ttl_seconds=120)
    _owned, row = await store.try_begin_invocation(_begin())
    assert row["attempt"] == 1
    assert row["attempt_token"] is not None
    assert row["lease_expires_at"] is not None

    conn = await store._connect()
    try:
        # The lease is in the future BY THE DATABASE'S RECKONING, not by the test process's.
        assert await conn.fetchval(
            "SELECT lease_expires_at > now() FROM reasoning_invocations WHERE invocation_id=$1",
            row["invocation_id"],
        )
    finally:
        await conn.close()


async def test_a_live_lease_cannot_be_taken_over():
    store = await _store_or_skip(lease_ttl_seconds=300)
    data = _begin()
    await store.try_begin_invocation(data)
    assert await store.try_take_over_invocation(data["correlation_id"]) is None


async def test_an_expired_lease_is_taken_over_by_exactly_one_of_eight_contenders():
    """C2/C3 at the store layer. A dead owner must not own forever, and recovery must not fan out
    into eight simultaneous provider calls."""
    store = await _store_or_skip(lease_ttl_seconds=300)
    data = _begin()
    await store.try_begin_invocation(data)
    await _expire_lease(store, data["correlation_id"])

    results = await asyncio.gather(
        *(store.try_take_over_invocation(data["correlation_id"]) for _ in range(8))
    )
    winners = [r for r in results if r is not None]
    assert len(winners) == 1, "exactly one contender may take over an expired lease"
    assert winners[0]["attempt"] == 2, "and the attempt advances exactly once"

    row = await _raw(store, data["correlation_id"])
    assert row["attempt"] == 2
    assert str(row["attempt_token"]) == str(winners[0]["attempt_token"])


async def test_a_terminal_invocation_is_never_taken_over():
    store = await _store_or_skip(lease_ttl_seconds=300)
    data = _begin()
    _owned, row = await store.try_begin_invocation(data)
    await store.complete_invocation(
        row["invocation_id"], attempt_token=row["attempt_token"], terminal=_terminal()
    )
    # Even with no lease left to respect, a finished call is not an abandoned one.
    assert await store.try_take_over_invocation(data["correlation_id"]) is None


async def test_a_legacy_unleased_started_row_is_recoverable_rather_than_owned_forever():
    """Rows claimed before migration 040 carry no lease. Reading that as 'unowned' is what lets a
    pre-contract stranded attempt finally make progress -- without rewriting its history."""
    store = await _store_or_skip(lease_ttl_seconds=300)
    data = _begin()
    _owned, row = await store.try_begin_invocation(data)

    # Exactly the shape a pre-040 claim left behind: owned by nobody identifiable, bounded by
    # nothing. Note that the CURRENT contract refuses to write this -- which is the point of the
    # constraint, and why reaching it requires standing where the constraint was not.
    await _as_pre_contract_row(
        store,
        row["invocation_id"],
        "UPDATE reasoning_invocations SET lease_expires_at=NULL, attempt_token=NULL "
        "WHERE invocation_id=$1",
    )

    taken = await store.try_take_over_invocation(data["correlation_id"])
    assert taken is not None, "a legacy started row is not owned forever"
    assert taken["attempt"] == 2
    assert taken["attempt_token"] is not None


# --- zombie safety ------------------------------------------------------------------------------


async def test_a_superseded_attempt_cannot_overwrite_the_attempt_that_replaced_it():
    """C3's dangerous half. Attempt 1's lease expires, attempt 2 takes over, and attempt 1 then
    returns from a provider call that really did happen. It must not win."""
    store = await _store_or_skip(lease_ttl_seconds=300)
    data = _begin()
    _owned, first = await store.try_begin_invocation(data)
    await _expire_lease(store, data["correlation_id"])
    second = await store.try_take_over_invocation(data["correlation_id"])
    assert second is not None

    zombie = await store.complete_invocation(
        first["invocation_id"],
        attempt_token=first["attempt_token"],
        terminal=_terminal(artifact=dict(_ARTIFACT, summary="the zombie's answer")),
    )
    assert zombie["status"] == "started", "the zombie's write is refused, not applied"
    assert zombie["artifact"] is None

    winner = await store.complete_invocation(
        second["invocation_id"],
        attempt_token=second["attempt_token"],
        terminal=_terminal(artifact=dict(_ARTIFACT, summary="the live owner's answer")),
    )
    assert winner["status"] == "succeeded"
    assert winner["artifact"]["summary"] == "the live owner's answer"

    row = await _raw(store, data["correlation_id"])
    assert json.loads(row["artifact"])["summary"] == "the live owner's answer"


async def test_exactly_one_terminal_outcome_survives_a_zombie_race():
    """Whichever order they arrive in, one artifact is canonical and one attempt is recorded as
    having produced it. Never two."""
    store = await _store_or_skip(lease_ttl_seconds=300)
    data = _begin()
    _owned, first = await store.try_begin_invocation(data)
    await _expire_lease(store, data["correlation_id"])
    second = await store.try_take_over_invocation(data["correlation_id"])

    outcomes = await asyncio.gather(
        store.complete_invocation(
            first["invocation_id"],
            attempt_token=first["attempt_token"],
            terminal=_terminal(artifact=dict(_ARTIFACT, summary="attempt one")),
        ),
        store.complete_invocation(
            second["invocation_id"],
            attempt_token=second["attempt_token"],
            terminal=_terminal(artifact=dict(_ARTIFACT, summary="attempt two")),
        ),
    )
    terminal = [o for o in outcomes if o["status"] == "succeeded"]
    assert len(terminal) >= 1
    summaries = {json.dumps(o["artifact"], sort_keys=True) for o in terminal}
    assert len(summaries) == 1, "the two attempts must not both become canonical"

    row = await _raw(store, data["correlation_id"])
    assert row["status"] == "succeeded"
    assert json.loads(row["artifact"])["summary"] == "attempt two"


# --- the service's replay contract ---------------------------------------------------------------


async def test_a_replay_returns_the_typed_artifact_and_calls_no_provider():
    """C4 at the reasoning layer: the artifact survives the process that produced it."""
    store = await _store_or_skip()
    correlation_id = str(uuid.uuid4())
    request = ReasoningRequest(
        verb="propose", context={"goal_statement": "g"}, correlation_id=correlation_id
    )

    class _CountingProvider(MockReasoningProvider):
        calls = 0

        def propose(self, req):
            type(self).calls += 1
            return super().propose(req)

    provider = _CountingProvider()
    first = await ReasoningService(store=store).invoke(request, provider=provider)
    assert first.disposition == "fresh"
    assert first.artifact is not None
    assert _CountingProvider.calls == 1

    # A brand-new service, as a new process would have.
    second = await ReasoningService(store=store).invoke(request, provider=provider)
    assert second.disposition == "replay"
    assert isinstance(second.artifact, ProposalArtifact)
    assert second.artifact == first.artifact, "the exact artifact, reparsed through its own model"
    assert _CountingProvider.calls == 1, "a replay invokes nothing"
    assert second.attempt == 1


async def test_a_replay_of_a_failure_carries_the_failure_and_no_artifact():
    store = await _store_or_skip()
    from shared.sdk.agent_reasoning.provider import DisabledReasoningProvider

    request = ReasoningRequest(verb="propose", context={}, correlation_id=str(uuid.uuid4()))
    first = await ReasoningService(store=store).invoke(
        request, provider=DisabledReasoningProvider()
    )
    assert first.invocation["status"] == "failed"

    second = await ReasoningService(store=store).invoke(request)
    assert second.disposition == "replay"
    assert second.artifact is None
    assert second.invocation["status"] == "failed"
    assert second.invocation["failure_category"] == first.invocation["failure_category"]


async def test_a_legacy_metadata_only_success_replays_honestly_rather_than_pretending():
    """Migration 040 preserves pre-contract rows instead of rewriting them. A replay of one has
    genuinely nothing to return, and says so -- it does not fabricate a plausible artifact."""
    store = await _store_or_skip()
    correlation_id = str(uuid.uuid4())
    _owned, row = await store.try_begin_invocation(_begin(correlation_id))

    await _as_pre_contract_row(
        store,
        row["invocation_id"],
        "UPDATE reasoning_invocations SET status='succeeded', completed_at=now(), "
        "lease_expires_at=NULL WHERE invocation_id=$1",
    )

    result = await ReasoningService(store=store).invoke(
        ReasoningRequest(verb="propose", context={}, correlation_id=correlation_id)
    )
    assert result.disposition == "replay"
    assert result.succeeded is True
    assert result.artifact is None, "nothing was stored, so nothing is returned"


async def test_a_corrupt_stored_artifact_is_raised_rather_than_silently_dropped():
    """Degrading to None here would recreate the exact stranding this rebaseline removed, while
    hiding a real defect behind it."""
    with pytest.raises(ReasoningArtifactCorruptError):
        ReasoningService.rehydrate(
            {
                "invocation_id": str(uuid.uuid4()),
                "status": "succeeded",
                "reasoning_verb": "propose",
                "artifact": {"not": "a proposal"},
            }
        )


async def test_an_in_progress_call_is_bounded_by_the_lease_not_forever():
    """The second way work used to strand: an owner that dies mid-call. A later caller now takes
    the attempt over and really does invoke the provider again -- at-least-once, honestly."""
    store = await _store_or_skip(lease_ttl_seconds=300)
    correlation_id = str(uuid.uuid4())
    request = ReasoningRequest(verb="propose", context={}, correlation_id=correlation_id)

    # A worker claims the call and dies without terminalizing it.
    _owned, row = await store.try_begin_invocation(_begin(correlation_id))

    live = await ReasoningService(store=store).invoke(request)
    assert live.disposition == "in_progress", "a live lease is respected"
    assert live.artifact is None

    # Time passes and the owner never comes back.
    await _expire_lease(store, correlation_id)
    recovered = await ReasoningService(store=store).invoke(request)
    assert recovered.disposition == "fresh", "an expired lease is taken over and really re-run"
    assert recovered.artifact is not None
    assert recovered.attempt == 2, "and the second provider attempt is recorded as one"

    final = await _raw(store, correlation_id)
    assert final["status"] == "succeeded"
    assert final["artifact"] is not None
    assert final["attempt"] == 2


async def test_an_exhausted_attempt_budget_fails_closed_instead_of_staying_started_forever():
    """Takeover is bounded. A worker that reliably dies must not produce an unbounded series of
    provider attempts -- but it must not leave the row 'started' forever either."""
    store = await _store_or_skip(lease_ttl_seconds=300, max_attempts=2)
    correlation_id = str(uuid.uuid4())
    await store.try_begin_invocation(_begin(correlation_id))
    await _expire_lease(store, correlation_id)
    assert await store.try_take_over_invocation(correlation_id) is not None  # attempt 2
    await _expire_lease(store, correlation_id)
    assert await store.try_take_over_invocation(correlation_id) is None, "budget spent"

    result = await ReasoningService(store=store).invoke(
        ReasoningRequest(verb="propose", context={}, correlation_id=correlation_id)
    )
    assert result.disposition == "replay"
    assert result.invocation["status"] == "failed"
    assert result.invocation["failure_category"] == "provider_unavailable"
    assert result.artifact is None

    row = await _raw(store, correlation_id)
    assert row["status"] == "failed"
    assert row["lease_expires_at"] is None
    assert row["attempt"] == 2, "the recorded attempt count is the truthful one"


async def test_eight_concurrent_callers_produce_one_artifact_and_one_provider_call():
    """A. the unexpired-owner case, against real PostgreSQL rather than cooperative scheduling."""
    store = await _store_or_skip(lease_ttl_seconds=300)
    correlation_id = str(uuid.uuid4())

    class _CountingProvider(MockReasoningProvider):
        calls = 0

        def propose(self, req):
            type(self).calls += 1
            return super().propose(req)

    provider = _CountingProvider()
    results = await asyncio.gather(
        *(
            ReasoningService(store=store).invoke(
                ReasoningRequest(verb="propose", context={}, correlation_id=correlation_id),
                provider=provider,
            )
            for _ in range(8)
        )
    )
    assert _CountingProvider.calls == 1, "one provider call for one correlation_id"
    assert len([r for r in results if r.disposition == "fresh"]) == 1

    row = await _raw(store, correlation_id)
    assert row["status"] == "succeeded" and row["attempt"] == 1

    # Everyone who got an artifact got the SAME artifact.
    artifacts = {r.artifact.model_dump_json() for r in results if r.artifact is not None}
    assert len(artifacts) == 1


# --- what is stored ------------------------------------------------------------------------------


async def test_the_stored_artifact_carries_no_prompt_completion_or_hidden_reasoning():
    store = await _store_or_skip()
    request = ReasoningRequest(
        verb="propose", context={"goal_statement": "g"}, correlation_id=str(uuid.uuid4())
    )
    await ReasoningService(store=store).invoke(request)
    row = await _raw(store, request.correlation_id)
    payload = row["artifact"]
    assert payload is not None
    for marker in (
        "chain_of_thought",
        "scratchpad",
        "raw_prompt",
        "system_prompt",
        "completion",
        "token_trace",
        "api_key",
        "credential",
        "secret",
    ):
        assert marker not in payload.lower(), marker
    # Only the artifact's own declared fields exist -- the model is closed, and this is what
    # closed means once the payload is durable.
    assert set(json.loads(payload)) == set(ProposalArtifact.model_fields)
