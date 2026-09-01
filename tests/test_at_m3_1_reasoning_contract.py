"""Step AT-M3.1 -- reasoning contract, provider abstraction and service, against fakes.

No DB, no network. Exercises the AT-M3.1 acceptance list end to end using
``InMemoryReasoningInvocationStore`` (tests/agent_reasoning_fakes.py), mirroring the existing
``test_at_m2_team_core.py`` convention of testing the service layer against an in-memory fake and
reserving real PostgreSQL for ``test_at_m3_1_reasoning_store.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.agent_reasoning.models import (
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ProposalArtifact,
    ReasoningRequest,
)
from shared.sdk.agent_reasoning.provider import (
    DisabledReasoningProvider,
    ReasoningProviderError,
    get_reasoning_provider,
)
from shared.sdk.agent_reasoning.mock_provider import MockReasoningProvider
from shared.sdk.agent_reasoning.service import ReasoningPersistenceError, ReasoningService
from tests.agent_reasoning_fakes import InMemoryReasoningInvocationStore
from tests.agent_team_fakes import RecordingAuditClient

# Fields a durable invocation row is PERMITTED to carry. Anything outside this set is a leak.
_PERMITTED_INVOCATION_FIELDS = {
    "invocation_id",
    "project_id",
    "thread_id",
    "requested_by_principal_id",
    "reasoning_verb",
    "requested_provider_name",
    "provider_mode",
    "model_name",
    "round_number",
    "status",
    "failure_category",
    "failure_reason",
    # AT-M3.4 (rebaselined). The record is no longer metadata-ONLY, and that is a deliberate,
    # bounded widening rather than a leak: `artifact` holds the SAME closed-schema, content-safety
    # screened payload a TeamMessage already carries, and holds it so that a succeeded call whose
    # caller died can be recovered instead of stranded. The forbidden-marker scan below is
    # unchanged and still applies -- no prompt, completion or hidden-reasoning field is admitted
    # by this list, and none could pass the artifact models' extra="forbid" anyway.
    "artifact_type",
    "artifact",
    "attempt",
    "attempt_token",
    "lease_expires_at",
    "outcome_ref",
    "input_tokens",
    "output_tokens",
    "estimated_cost_usd",
    "latency_ms",
    "correlation_id",
    "audit_ref",
    "started_at",
    "completed_at",
    "created_at",
}

_FORBIDDEN_FIELD_MARKERS = (
    "prompt",
    "completion",
    "chain_of_thought",
    "raw_reasoning",
    "hidden_reasoning",
    "scratchpad",
    "token_trace",
)


def _service() -> tuple[ReasoningService, InMemoryReasoningInvocationStore, RecordingAuditClient]:
    store = InMemoryReasoningInvocationStore()
    audit = RecordingAuditClient()
    return ReasoningService(store=store, audit_client=audit), store, audit


# --- 1/2/3: each verb produces a valid structured artifact via the mock provider -------------------


async def test_mock_propose_returns_a_valid_proposal_artifact():
    service, _, _ = _service()
    request = ReasoningRequest(verb="propose", context={"goal_statement": "Build a todo API"})
    result = await service.invoke(request)
    assert result.succeeded
    assert isinstance(result.artifact, ProposalArtifact)
    assert result.artifact.summary
    assert result.artifact.rationale_summary
    assert result.artifact.recommendation


async def test_mock_critique_returns_a_valid_critique_artifact():
    service, _, _ = _service()
    request = ReasoningRequest(
        verb="critique", context={"proposal_summary": "use FastAPI with SQLite"}
    )
    result = await service.invoke(request)
    assert result.succeeded
    assert isinstance(result.artifact, CritiqueArtifact)
    assert result.artifact.recommendation


async def test_mock_summarize_decision_returns_a_valid_decision_summary_artifact():
    service, _, _ = _service()
    request = ReasoningRequest(
        verb="summarize_decision",
        context={"options_considered": ["FastAPI", "Flask"], "selected_option": "FastAPI"},
    )
    result = await service.invoke(request)
    assert result.succeeded
    assert isinstance(result.artifact, DecisionSummaryArtifact)
    assert result.artifact.selected_option == "FastAPI"
    assert result.artifact.options_considered == ("FastAPI", "Flask")


# --- 4: durable ReasoningInvocation row created -----------------------------------------------------


async def test_a_successful_call_records_a_durable_invocation_row():
    service, store, _ = _service()
    request = ReasoningRequest(verb="propose", context={"goal_statement": "Build a todo API"})
    result = await service.invoke(request)
    stored = await store.get_by_correlation_id(request.correlation_id)
    assert stored is not None
    assert stored["invocation_id"] == result.invocation["invocation_id"]
    assert stored["status"] == "succeeded"


# --- 5: mode is unmistakably mock --------------------------------------------------------------------


async def test_a_mock_call_is_unambiguously_marked_mock():
    service, _, _ = _service()
    request = ReasoningRequest(verb="propose", context={})
    result = await service.invoke(request)
    assert result.invocation["provider_mode"] == "mock"
    assert result.invocation["requested_provider_name"] == "mock"


# --- 6: no raw prompt/completion/CoT persisted -------------------------------------------------------


async def test_the_invocation_record_carries_metadata_only():
    service, _, _ = _service()
    request = ReasoningRequest(verb="propose", context={"goal_statement": "Build a todo API"})
    result = await service.invoke(request)
    leaked_fields = set(result.invocation) - _PERMITTED_INVOCATION_FIELDS
    assert leaked_fields == set(), f"unexpected field(s) on the invocation record: {leaked_fields}"
    for field_name in result.invocation:
        assert not any(marker in field_name.lower() for marker in _FORBIDDEN_FIELD_MARKERS), (
            field_name
        )


# --- 7: forbidden nested content rejected -------------------------------------------------------------


def test_a_request_context_carrying_hidden_reasoning_is_rejected_at_construction():
    with pytest.raises(ValidationError):
        ReasoningRequest(verb="propose", context={"chain_of_thought": "the real reasoning"})


def test_a_request_context_carrying_a_secret_marker_is_rejected_at_construction():
    with pytest.raises(ValidationError):
        ReasoningRequest(verb="propose", context={"api_key": "sk-super-secret"})


def test_a_nested_forbidden_key_is_also_rejected():
    with pytest.raises(ValidationError):
        ReasoningRequest(verb="propose", context={"notes": [{"meta": {"raw_prompt": "leak"}}]})


# --- 8: malformed provider output fails closed --------------------------------------------------------


class _WrongTypeProvider:
    name = "misbehaving"
    mode = "mock"

    def propose(self, request: ReasoningRequest) -> object:
        return {"summary": "not a real artifact"}  # the wrong shape entirely

    def critique(self, request: ReasoningRequest) -> object:
        raise NotImplementedError

    def summarize_decision(self, request: ReasoningRequest) -> object:
        raise NotImplementedError


async def test_a_provider_returning_the_wrong_shape_fails_closed():
    service, _, _ = _service()
    request = ReasoningRequest(verb="propose", context={})
    result = await service.invoke(request, provider=_WrongTypeProvider())
    assert not result.succeeded
    assert result.artifact is None
    assert result.invocation["status"] == "failed"
    assert result.invocation["failure_category"] == "malformed_output"


# --- 9: disabled provider fails closed ------------------------------------------------------------------


async def test_the_disabled_provider_fails_closed_and_never_returns_an_artifact():
    service, _, _ = _service()
    request = ReasoningRequest(verb="propose", context={})
    result = await service.invoke(request, provider=DisabledReasoningProvider())
    assert not result.succeeded
    assert result.artifact is None
    assert result.invocation["status"] == "failed"
    assert result.invocation["failure_category"] == "provider_disabled"


def test_disabled_provider_raises_directly_for_every_verb():
    provider = DisabledReasoningProvider()
    request = ReasoningRequest(verb="propose", context={})
    for verb in ("propose", "critique", "summarize_decision"):
        with pytest.raises(ReasoningProviderError):
            getattr(provider, verb)(request)


# --- 10/11: unknown / external provider names fail closed, no network path exists ------------------------


@pytest.mark.parametrize(
    "requested_name",
    ["not_a_real_provider", "external_openai", "external_anthropic", "external_openai_placeholder"],
)
async def test_unknown_and_external_provider_names_fail_closed(requested_name):
    service, _, _ = _service()
    resolved = get_reasoning_provider(requested_name)
    assert isinstance(resolved, DisabledReasoningProvider)
    assert resolved.mode == "disabled"
    request = ReasoningRequest(verb="propose", context={}, provider_name=requested_name)
    result = await service.invoke(request, provider=resolved)
    assert not result.succeeded
    assert result.artifact is None
    assert result.invocation["provider_mode"] == "disabled"
    assert result.invocation["failure_category"] == "provider_unauthorized"
    # The requested name is preserved verbatim for audit, distinct from an explicit 'disabled'.
    assert result.invocation["requested_provider_name"] == requested_name


def test_no_network_client_is_importable_from_this_package():
    """AT-M3.1 ships no live adapter. Nothing in the package imports a network library."""
    import ast
    from pathlib import Path

    package_dir = Path(__file__).resolve().parents[1] / "shared" / "sdk" / "agent_reasoning"
    network_markers = {"httpx", "requests", "aiohttp", "socket", "urllib"}
    for path in package_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            leaked = names & network_markers
            assert not leaked, f"{path.name} imports a network library: {leaked}"


# --- 12: provider refusal never substitutes a mock success -------------------------------------------------


async def test_refusal_never_produces_an_artifact_indistinguishable_from_a_real_one():
    """The old Stage-30 ExternalLLMProviderGuard pattern -- downgrading a refusal to a
    mock-authored, confidence-capped 'success' -- must NOT be inherited here. A refusal is
    recorded as failed with no artifact, full stop.
    """
    service, _, _ = _service()
    request = ReasoningRequest(verb="propose", context={}, provider_name="external_anthropic")
    result = await service.invoke(request)
    assert result.artifact is None
    assert result.invocation["status"] == "failed"


# --- 13: duplicate correlation does not create a duplicate authoritative outcome ---------------------------


async def test_a_replayed_correlation_id_resolves_to_the_original_row_only():
    service, store, _ = _service()
    request = ReasoningRequest(verb="propose", context={"goal_statement": "Build a todo API"})
    first = await service.invoke(request)
    second = await service.invoke(request)  # same correlation_id -- a genuine replay
    assert first.disposition == "fresh"
    assert second.disposition == "replay"
    assert first.invocation["invocation_id"] == second.invocation["invocation_id"]
    assert second.succeeded, "the replayed row's recorded OUTCOME is still 'succeeded'"
    assert len(store.rows_by_correlation) == 1

    # AT-M3.4 (rebaselined) changed this line's meaning, and the change is the point. A replay
    # used to return artifact=None because artifact CONTENT was never persisted -- which is
    # exactly how a succeeded call whose caller died became permanently unrecoverable. The
    # artifact is now RECOVERED from the durable row: same content, still no second provider call.
    assert second.artifact is not None, "a replay must recover the artifact, not lose it"
    assert second.artifact == first.artifact
    assert second.disposition == "replay", "recovering it is not the same as invoking again"


async def test_two_distinct_calls_get_two_distinct_rows():
    service, store, _ = _service()
    first = await service.invoke(ReasoningRequest(verb="propose", context={"a": "1"}))
    second = await service.invoke(ReasoningRequest(verb="propose", context={"a": "2"}))
    assert first.disposition == second.disposition == "fresh"
    assert first.invocation["invocation_id"] != second.invocation["invocation_id"]
    assert len(store.rows_by_correlation) == 2


async def test_a_replay_of_a_prior_failure_is_explicitly_a_replay_not_a_fresh_failure():
    """Validation 1 finding: replay-of-failure and a brand-new independent failure used to be
    structurally identical. disposition is what tells them apart now."""
    service, store, _ = _service()
    request = ReasoningRequest(verb="propose", context={"goal_statement": "g"})
    first = await service.invoke(request, provider=DisabledReasoningProvider())
    second = await service.invoke(request)  # same correlation_id, provider arg irrelevant now
    third = await service.invoke(
        ReasoningRequest(verb="propose", context={"goal_statement": "g2"}),
        provider=DisabledReasoningProvider(),
    )
    assert first.disposition == "fresh"
    assert second.disposition == "replay"
    assert third.disposition == "fresh"
    assert not first.succeeded and not second.succeeded and not third.succeeded
    assert second.invocation["invocation_id"] == first.invocation["invocation_id"]
    assert third.invocation["invocation_id"] != first.invocation["invocation_id"]


async def test_replay_of_an_in_progress_invocation_is_explicitly_in_progress():
    """A correlation_id whose row is still 'started' (owner has not reached a terminal outcome)
    must be observable as in_progress, never as a fresh call and never as a replay of a result
    that doesn't exist yet."""
    store = InMemoryReasoningInvocationStore()
    service = ReasoningService(store=store, audit_client=None)
    correlation_id = "22222222-2222-2222-2222-222222222222"
    owned, row = await store.try_begin_invocation(
        {
            "reasoning_verb": "propose",
            "requested_provider_name": "mock",
            "provider_mode": "mock",
            "round_number": 1,
            "correlation_id": correlation_id,
            "started_at": None,
        }
    )
    assert owned
    assert row["status"] == "started"

    duplicate = await service.invoke(
        ReasoningRequest(verb="propose", context={}, correlation_id=correlation_id)
    )
    assert duplicate.disposition == "in_progress"
    assert duplicate.artifact is None
    assert duplicate.invocation["status"] == "started"


# --- audit is best-effort and non-fatal --------------------------------------------------------------------


async def test_a_missing_audit_client_never_breaks_a_call():
    store = InMemoryReasoningInvocationStore()
    service = ReasoningService(store=store, audit_client=None)
    result = await service.invoke(ReasoningRequest(verb="critique", context={}))
    assert result.succeeded
    assert result.invocation["audit_ref"] is None


async def test_every_successful_call_is_audited_when_a_client_is_present():
    service, _, audit = _service()
    await service.invoke(ReasoningRequest(verb="propose", context={}))
    # One attempt, one terminal outcome. AT-M3.4 (rebaselined) split these because an invocation
    # can now be attempted more than once, and "how many times was a provider actually asked" has
    # to be answerable from the audit trail rather than assumed to be one.
    assert audit.decision_types() == ["reasoning_attempt_started", "reasoning_invoked"]


async def test_a_replay_is_never_audited_as_another_successful_invocation():
    """A recovered result is not a second reasoning call, and the audit trail must not imply it
    was -- otherwise every crash recovery would inflate the number of provider calls on record."""
    service, _, audit = _service()
    request = ReasoningRequest(verb="propose", context={})
    await service.invoke(request)
    await service.invoke(request)
    assert audit.decision_types() == [
        "reasoning_attempt_started",
        "reasoning_invoked",
        "reasoning_replayed",
    ]
    assert audit.decision_types().count("reasoning_invoked") == 1


# --- AT-M3.1-REMEDIATION-1: durability under terminal-persistence failure (Validation 1 blocker 1) ---


class _StartedThenCrashingStore:
    """A 'started' row is genuinely inserted (matching the real store's ordering), but the
    TERMINAL write is made to fail -- simulating a dropped DB connection right after the provider
    already produced a real artifact."""

    def __init__(self) -> None:
        self.backing = InMemoryReasoningInvocationStore()
        self.complete_invocation_calls = 0

    async def try_begin_invocation(self, data):
        return await self.backing.try_begin_invocation(data)

    async def complete_invocation(self, invocation_id, *, attempt_token, terminal):
        self.complete_invocation_calls += 1
        raise ConnectionResetError("simulated: DB connection dropped mid-write")

    async def get_by_correlation_id(self, correlation_id):
        return await self.backing.get_by_correlation_id(correlation_id)


async def test_a_terminal_persistence_failure_never_returns_the_artifact_as_success():
    store = _StartedThenCrashingStore()
    service = ReasoningService(store=store, audit_client=None)
    request = ReasoningRequest(verb="propose", context={"goal_statement": "g"})

    with pytest.raises(ReasoningPersistenceError) as excinfo:
        await service.invoke(request)

    assert excinfo.value.correlation_id == request.correlation_id
    assert store.complete_invocation_calls == 1


async def test_the_started_row_survives_a_terminal_persistence_failure():
    """Validation 1's central finding: an invocation must not vanish just because the terminal
    write failed. The 'started' row -- inserted BEFORE the provider ran -- is durable evidence
    that the attempt occurred, and it must still be there afterwards."""
    store = _StartedThenCrashingStore()
    service = ReasoningService(store=store, audit_client=None)
    request = ReasoningRequest(verb="propose", context={"goal_statement": "g"})

    with pytest.raises(ReasoningPersistenceError) as excinfo:
        await service.invoke(request)

    surviving_row = await store.get_by_correlation_id(request.correlation_id)
    assert surviving_row is not None, "the started row must not be lost"
    assert surviving_row["invocation_id"] == excinfo.value.invocation_id
    assert surviving_row["status"] == "started"


async def test_persistence_failure_does_not_silently_reinvoke_the_provider():
    store = _StartedThenCrashingStore()
    service = ReasoningService(store=store, audit_client=None)
    request = ReasoningRequest(verb="propose", context={"goal_statement": "g"})
    call_count = {"n": 0}

    class _CountingMock(MockReasoningProvider):
        def propose(self, req):
            call_count["n"] += 1
            return super().propose(req)

    with pytest.raises(ReasoningPersistenceError):
        await service.invoke(request, provider=_CountingMock())
    assert call_count["n"] == 1, "the service must not retry the provider on a persistence failure"


# --- AT-M3.1-REMEDIATION-1: single execution owner under concurrent duplicates (blocker 2) -----------


async def test_concurrent_duplicate_correlation_invokes_the_provider_at_most_once():
    """The store-level race Validation 1 proved under real PostgreSQL (10/10 concurrent callers
    each invoking the provider). Reproduced here at the store-ownership level with the in-memory
    fake: only the winner of try_begin_invocation may call the provider at all."""
    store = InMemoryReasoningInvocationStore()
    correlation_id = "33333333-3333-3333-3333-333333333333"
    winners = 0
    for _ in range(10):
        owned, _row = await store.try_begin_invocation(
            {
                "reasoning_verb": "propose",
                "requested_provider_name": "mock",
                "provider_mode": "mock",
                "round_number": 1,
                "correlation_id": correlation_id,
                "started_at": None,
            }
        )
        if owned:
            winners += 1
    assert winners == 1, "exactly one of ten claim attempts may own execution"
    assert len(store.rows_by_correlation) == 1


async def test_losing_callers_never_receive_an_artifact_attributed_to_a_different_invocation():
    """Validation 1's most severe finding: racing callers each received a genuinely different,
    self-computed artifact paired with the SAME (winning) invocation_id -- an attribution
    mismatch. Under the new contract, a losing caller never calls the provider.

    AT-M3.4 (rebaselined) sharpened what it then receives. It used to receive nothing, which was
    safe but unrecoverable. It now receives the WINNER'S OWN artifact, read back from the durable
    row -- so attribution is not merely un-mismatched, it is exact: every caller of one
    correlation_id sees byte-identical content produced by exactly one provider call."""
    store = InMemoryReasoningInvocationStore()
    service = ReasoningService(store=store, audit_client=None)
    correlation_id = "44444444-4444-4444-4444-444444444444"
    request = ReasoningRequest(
        verb="propose", context={"goal_statement": "g"}, correlation_id=correlation_id
    )

    first = await service.invoke(request)
    assert first.disposition == "fresh"
    assert first.artifact is not None

    for _ in range(5):
        loser = await service.invoke(request)
        assert loser.disposition == "replay", "a loser never invokes the provider"
        assert loser.invocation["invocation_id"] == first.invocation["invocation_id"]
        assert loser.artifact == first.artifact, "the recovered artifact is the winner's own"
        assert loser.invocation["attempt"] == 1, "no loser caused a second attempt"


# --- AT-M3.1-REMEDIATION-1: failure_reason cannot carry forbidden/secret content (blocker 3) ----------


async def test_an_unexpected_provider_exceptions_message_is_never_persisted_verbatim():
    """Validation 1 finding 8b: a leaky/misbehaving provider's exception message used to be
    persisted verbatim (chain_of_thought / API-key-shaped text and all)."""
    store = InMemoryReasoningInvocationStore()
    service = ReasoningService(store=store, audit_client=None)

    class _LeakyProvider:
        name = "buggy-vendor-adapter"
        mode = "mock"

        def propose(self, request):
            raise RuntimeError(
                "vendor call failed; raw_completion='chain_of_thought: I will pretend to agree "
                "because...'; Authorization: Bearer sk-ant-api03-REALLYLEAKEDKEY123456"
            )

        def critique(self, request):
            raise NotImplementedError

        def summarize_decision(self, request):
            raise NotImplementedError

    result = await service.invoke(
        ReasoningRequest(verb="propose", context={}), provider=_LeakyProvider()
    )
    reason = result.invocation["failure_reason"]
    assert reason == "unexpected_provider_error:RuntimeError"
    for marker in ("chain_of_thought", "sk-ant-", "Bearer", "REALLYLEAKEDKEY"):
        assert marker not in reason


async def test_direct_store_use_cannot_persist_an_unsafe_failure_reason():
    """Validation 1 finding 8a: calling the store directly (bypassing ReasoningService entirely)
    used to accept a forbidden-marker-shaped failure_reason with no rejection or redaction --
    now sanitized at the store layer too, defense-in-depth, mirroring TeamStore.post_message."""
    store = InMemoryReasoningInvocationStore()
    correlation_id = "55555555-5555-5555-5555-555555555555"
    owned, row = await store.try_begin_invocation(
        {
            "reasoning_verb": "propose",
            "requested_provider_name": "mock",
            "provider_mode": "mock",
            "round_number": 1,
            "correlation_id": correlation_id,
            "started_at": None,
        }
    )
    assert owned
    completed = await store.complete_invocation(
        row["invocation_id"],
        attempt_token=row["attempt_token"],
        terminal={
            "status": "failed",
            "failure_category": "provider_unavailable",
            "failure_reason": "chain_of_thought: the real reasoning was X; api_key=sk-ant-leak",
            "latency_ms": 1,
            "audit_ref": None,
            "completed_at": None,
        },
    )
    assert completed["failure_reason"] == "reason_redacted:forbidden_marker_detected"
    assert "chain_of_thought" not in completed["failure_reason"]
    assert "sk-ant-leak" not in completed["failure_reason"]


async def test_a_credential_shaped_failure_reason_is_redacted_not_just_keyword_matched():
    store = InMemoryReasoningInvocationStore()
    correlation_id = "66666666-6666-6666-6666-666666666666"
    _owned, row = await store.try_begin_invocation(
        {
            "reasoning_verb": "propose",
            "requested_provider_name": "mock",
            "provider_mode": "mock",
            "round_number": 1,
            "correlation_id": correlation_id,
            "started_at": None,
        }
    )
    completed = await store.complete_invocation(
        row["invocation_id"],
        attempt_token=row["attempt_token"],
        terminal={
            "status": "failed",
            "failure_category": "provider_unavailable",
            "failure_reason": "auth failed: Authorization: Bearer sk-ant-api03-abcdefghijklmnop",
            "latency_ms": 1,
            "audit_ref": None,
            "completed_at": None,
        },
    )
    assert "sk-ant-api03-abcdefghijklmnop" not in completed["failure_reason"]


async def test_ordinary_failure_reasons_survive_sanitization_unremarkably():
    """The safety net must not swallow every failure message -- only unsafe-shaped ones."""
    store = InMemoryReasoningInvocationStore()
    correlation_id = "77777777-7777-7777-7777-777777777777"
    _owned, row = await store.try_begin_invocation(
        {
            "reasoning_verb": "propose",
            "requested_provider_name": "mock",
            "provider_mode": "mock",
            "round_number": 1,
            "correlation_id": correlation_id,
            "started_at": None,
        }
    )
    completed = await store.complete_invocation(
        row["invocation_id"],
        attempt_token=row["attempt_token"],
        terminal={
            "status": "failed",
            "failure_category": "provider_unavailable",
            "failure_reason": "connection refused by upstream",
            "latency_ms": 1,
            "audit_ref": None,
            "completed_at": None,
        },
    )
    assert completed["failure_reason"] == "connection refused by upstream"


# --- AT-M3.1-REMEDIATION-1: mock rows cannot advertise a live model identity (advisory, section 8) ----


async def test_model_name_is_normalized_to_none_for_the_mock_provider():
    service, _, _ = _service()
    request = ReasoningRequest(
        verb="propose",
        context={"goal_statement": "g"},
        provider_name="mock",
        model_name="claude-opus-5-20260315",
    )
    result = await service.invoke(request)
    assert result.invocation["provider_mode"] == "mock"
    assert result.invocation["model_name"] is None
