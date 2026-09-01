"""Step AT-M3.1 -- the reasoning service: request -> durable claim -> provider -> safety -> outcome.

The layer that turns the vendor-neutral provider protocol and the plain store into one call a
future discussion loop (AT-M3.3) can use without knowing which provider answered, how the result
got persisted, or whether this particular call was the first to use its correlation_id.

Pipeline (AT-M3.1-REMEDIATION-1, Validation 1 blocker 1+2 fix):

    request -> resolve provider -> ATOMICALLY CLAIM correlation_id (durable 'started' row,
    BEFORE any provider call) -> [only the claim's owner reaches further] invoke verb ->
    validate artifact type -> content-safety check -> atomically persist terminal outcome
    -> return (artifact, invocation, disposition)

The claim is what closes the two blockers Validation 1 found: a provider is never invoked by a
caller that did not win the claim (closes duplicate/concurrent provider invocation and
artifact/evidence misattribution), and the 'started' row exists BEFORE the provider ever runs
(closes the "invocation occurred, zero durable evidence" gap -- if the terminal write later fails,
the 'started' row is already durable; nothing is silently lost, and the artifact is never returned
as an authoritative success by a call whose terminal outcome could not be persisted).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

from shared.sdk.agent_reasoning import events as reasoning_events
from shared.sdk.agent_reasoning.models import (
    ARTIFACT_TYPE_FOR_VERB,
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ExecutionDisposition,
    PlanDraftArtifact,
    ProposalArtifact,
    ReasoningRequest,
)
from shared.sdk.agent_reasoning.provider import (
    ReasoningProvider,
    ReasoningProviderError,
    get_reasoning_provider,
)
from shared.sdk.agent_reasoning.store import ReasoningInvocationStore

ReasoningArtifact = (
    ProposalArtifact | CritiqueArtifact | DecisionSummaryArtifact | PlanDraftArtifact
)

# Provider modes for which a model identity is meaningful. Neither mode this slice implements
# (mock, disabled) ever uses a real model, so model_name is nulled out server-side regardless of
# what a caller supplied -- a row must never read provider_mode='mock' next to a live-model-looking
# model_name. A future live mode is added here explicitly, not inferred.
_MODES_WITH_REAL_MODEL_IDENTITY: frozenset[str] = frozenset()


class ReasoningPersistenceError(RuntimeError):
    """The provider ran and produced a terminal outcome, but that outcome could not be durably
    recorded (e.g. a dropped DB connection during the terminal write).

    A durable 'started' row already exists for this correlation_id -- inserted BEFORE the provider
    was called -- so the attempt is not evidence-less; it is left non-terminal. The artifact is
    deliberately NOT attached to this exception and NOT returned to the caller as a successful
    result: a persistence failure must never look like success, and the caller must not silently
    re-invoke the provider for the same correlation_id (a fresh call would be rejected by the
    still-'started' row anyway, per ``try_begin_invocation``).
    """

    def __init__(self, *, invocation_id: str, correlation_id: str, cause: Exception) -> None:
        self.invocation_id = invocation_id
        self.correlation_id = correlation_id
        super().__init__(
            f"reasoning invocation {invocation_id} (correlation_id={correlation_id}) ran but its "
            f"terminal outcome could not be persisted: {type(cause).__name__}. A durable "
            "'started' row exists for this correlation_id and was not lost."
        )


@dataclass
class ReasoningResult:
    """One call's outcome, plus the execution provenance a caller MUST check before trusting it.

    ``artifact`` is populated if and only if ``disposition == "fresh"`` AND
    ``invocation["status"] == "succeeded"``. A ``"replay"`` or ``"in_progress"`` disposition NEVER
    carries an artifact -- artifact CONTENT is never persisted, only call metadata is, so there is
    nothing to reconstruct. Checking ``.succeeded`` alone is not sufficient to know whether
    ``artifact`` is present: a replay of a prior success is ``succeeded=True`` with
    ``artifact=None`` by design, and ``disposition`` is what tells the two apart.
    """

    artifact: ReasoningArtifact | None
    invocation: dict[str, Any]
    disposition: ExecutionDisposition

    @property
    def succeeded(self) -> bool:
        """The underlying invocation's recorded OUTCOME -- NOT whether ``artifact`` is populated.
        Use ``disposition == "fresh"`` (equivalently, ``artifact is not None``) to know whether
        this call is the one that produced a newly-authoritative artifact."""
        return self.invocation.get("status") == "succeeded"


class ReasoningService:
    def __init__(
        self,
        store: Any | None = None,
        audit_client: Any | None = None,
    ) -> None:
        self.store = store if store is not None else ReasoningInvocationStore()
        self.audit_client = audit_client

    async def _audit(
        self, decision_type: str, summary: str, result: str, refs: dict[str, Any]
    ) -> str | None:
        if self.audit_client is None:
            return None
        try:
            event = self.audit_client.build_audit_event(
                agent="reasoning-runtime",
                decision_type=decision_type,
                summary=summary,
                result=result,
                artifact_refs=refs,
            )
            return await self.audit_client.write_audit_event(event)
        except Exception:
            return None

    async def invoke(
        self,
        request: ReasoningRequest,
        provider: ReasoningProvider | None = None,
    ) -> ReasoningResult:
        """Run one reasoning call under an atomically-claimed durable invocation.

        Raises :class:`ReasoningPersistenceError` if the provider produced a terminal outcome that
        could not be durably recorded -- callers must treat that as "unknown, needs investigation
        for this correlation_id", never as a completed call.
        """
        resolved_provider = (
            provider if provider is not None else get_reasoning_provider(request.provider_name)
        )
        expected_type = ARTIFACT_TYPE_FOR_VERB[request.verb]
        model_name = (
            request.model_name
            if resolved_provider.mode in _MODES_WITH_REAL_MODEL_IDENTITY
            else None
        )

        started_at = datetime.now(timezone.utc)
        clock_start = time.monotonic()

        owned, row = await self.store.try_begin_invocation(
            {
                "project_id": request.project_id,
                "thread_id": request.thread_id,
                "requested_by_principal_id": request.requested_by_principal_id,
                "reasoning_verb": request.verb,
                "requested_provider_name": request.provider_name or resolved_provider.name,
                "provider_mode": resolved_provider.mode,
                "model_name": model_name,
                "round_number": request.round_number,
                "correlation_id": request.correlation_id,
                "started_at": started_at,
            }
        )
        if not owned:
            # Another caller (this attempt's real owner) already claimed this correlation_id --
            # no provider call happens here, and no artifact is fabricated to go with it.
            disposition: ExecutionDisposition = (
                "in_progress" if row.get("status") == "started" else "replay"
            )
            return ReasoningResult(artifact=None, invocation=row, disposition=disposition)

        invocation_id = row["invocation_id"]

        status = "failed"
        failure_category: str | None = None
        failure_reason: str | None = None
        artifact: ReasoningArtifact | None = None

        verb_method = getattr(resolved_provider, request.verb, None)
        if verb_method is None:
            failure_category = "provider_unavailable"
            failure_reason = f"provider has no {request.verb!r} verb"
        else:
            try:
                raw = verb_method(request)
            except ReasoningProviderError as exc:
                # Our own controlled exception type -- still routed through the store's
                # sanitize_failure_reason before persistence (defense-in-depth: its message can
                # embed a caller-supplied provider_name).
                failure_reason = str(exc)
                failure_category = (
                    "provider_disabled"
                    if getattr(resolved_provider, "name", "") == "disabled"
                    else "provider_unauthorized"
                )
            except Exception as exc:  # a misbehaving provider must not crash the caller
                # UNTRUSTED: an unknown exception's message can contain anything a misbehaving or
                # adversarial provider put there, including echoed wire content. Only the
                # exception's CLASS name is safe to persist as-is; the message itself is dropped
                # rather than pattern-matched, because "probably safe after redaction" is not the
                # bar here.
                failure_reason = f"unexpected_provider_error:{type(exc).__name__}"
                failure_category = "provider_unavailable"
            else:
                if not isinstance(raw, expected_type):
                    failure_category = "malformed_output"
                    failure_reason = f"expected {expected_type.__name__}, got {type(raw).__name__}"
                else:
                    try:
                        raw.as_safe_dict()
                    except ValueError as exc:
                        failure_category = "content_safety_rejected"
                        failure_reason = str(exc)
                    else:
                        # isinstance(raw, expected_type) already proved raw is one of the three
                        # known artifact subtypes; expected_type's static type
                        # (type[_StrictArtifact]) is just too coarse for mypy to narrow from.
                        artifact = cast(ReasoningArtifact, raw)
                        status = "succeeded"

        latency_ms = int((time.monotonic() - clock_start) * 1000)
        completed_at = datetime.now(timezone.utc)

        audit_ref = await self._audit(
            reasoning_events.AUDIT_REASONING_INVOKED,
            f"{request.verb} via {resolved_provider.name} ({resolved_provider.mode}): {status}",
            status,
            {
                "verb": request.verb,
                "provider_name": resolved_provider.name,
                "provider_mode": resolved_provider.mode,
                "project_id": request.project_id,
                "thread_id": request.thread_id,
                "round_number": request.round_number,
                "failure_category": failure_category,
                "correlation_id": request.correlation_id,
            },
        )

        try:
            completed = await self.store.complete_invocation(
                invocation_id,
                terminal={
                    "status": status,
                    "failure_category": failure_category,
                    "failure_reason": failure_reason,
                    "latency_ms": latency_ms,
                    "audit_ref": audit_ref,
                    "completed_at": completed_at,
                },
            )
        except Exception as exc:
            # The provider already ran; the durable 'started' row (inserted before the provider
            # was called) already exists. Only the terminal write failed -- never substitute the
            # artifact as an authoritative success, and never silently retry here.
            raise ReasoningPersistenceError(
                invocation_id=str(invocation_id),
                correlation_id=str(request.correlation_id),
                cause=exc,
            ) from exc

        if completed is None:
            # The row this call itself just inserted cannot legitimately vanish; treat it the
            # same as any other terminal-persistence anomaly rather than fabricate a result.
            raise ReasoningPersistenceError(
                invocation_id=str(invocation_id),
                correlation_id=str(request.correlation_id),
                cause=RuntimeError("complete_invocation returned no row for a known invocation_id"),
            )

        return ReasoningResult(artifact=artifact, invocation=completed, disposition="fresh")


__all__ = ["ReasoningArtifact", "ReasoningPersistenceError", "ReasoningResult", "ReasoningService"]
