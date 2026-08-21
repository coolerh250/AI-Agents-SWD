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
from shared.sdk.agent_reasoning.service import ReasoningService
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
        assert not any(
            marker in field_name.lower() for marker in _FORBIDDEN_FIELD_MARKERS
        ), field_name


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
    assert first.invocation["invocation_id"] == second.invocation["invocation_id"]
    assert second.artifact is None, "a replay must not re-derive artifact content"
    assert len(store.rows_by_correlation) == 1


async def test_two_distinct_calls_get_two_distinct_rows():
    service, store, _ = _service()
    first = await service.invoke(ReasoningRequest(verb="propose", context={"a": "1"}))
    second = await service.invoke(ReasoningRequest(verb="propose", context={"a": "2"}))
    assert first.invocation["invocation_id"] != second.invocation["invocation_id"]
    assert len(store.rows_by_correlation) == 2


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
    assert audit.decision_types() == ["reasoning_invoked"]
