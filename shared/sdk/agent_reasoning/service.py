"""Step AT-M3.1 -- the reasoning service: request -> provider -> safety -> durable evidence.

The layer that turns the vendor-neutral provider protocol and the plain store into one call a
future discussion loop (AT-M3.3) can use without knowing which provider answered or how the result
got persisted.

Pipeline, always in this order:

    request -> resolve provider -> invoke verb -> validate artifact type -> content-safety check
             -> record ReasoningInvocation -> return (artifact, invocation)

A failure at any step still produces a durable, audited ``failed`` invocation row wherever a
database is reachable to write it to -- the same "evidence first, never silent" posture
``TeamService.decide_route`` already established for routing decisions. Nothing here ever
substitutes a mock-authored artifact for a refused or malformed one: a failed step returns no
artifact, only the record of why.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

from shared.sdk.agent_reasoning import events as reasoning_events
from shared.sdk.agent_reasoning.models import (
    ARTIFACT_TYPE_FOR_VERB,
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ProposalArtifact,
    ReasoningRequest,
)
from shared.sdk.agent_reasoning.provider import (
    ReasoningProvider,
    ReasoningProviderError,
    get_reasoning_provider,
)
from shared.sdk.agent_reasoning.store import ReasoningInvocationStore

ReasoningArtifact = ProposalArtifact | CritiqueArtifact | DecisionSummaryArtifact


@dataclass
class ReasoningResult:
    """One call's outcome: the artifact (only on success) and its durable metadata record."""

    artifact: ReasoningArtifact | None
    invocation: dict[str, Any]

    @property
    def succeeded(self) -> bool:
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
        """Run one reasoning call and return its artifact plus durable evidence.

        A replayed ``correlation_id`` short-circuits before the provider is ever called: the
        original invocation row is authoritative and is returned as-is. Because artifact CONTENT
        is never persisted (only call metadata is), a replay carries no artifact -- callers must
        treat a repeated ``correlation_id`` as already handled, not as a way to re-fetch content.
        This also means a live provider (a future slice) is never invoked twice for one logical
        attempt.
        """
        with contextlib.suppress(Exception):
            existing = await self.store.get_by_correlation_id(request.correlation_id)
            if existing is not None:
                return ReasoningResult(artifact=None, invocation=existing)

        resolved_provider = (
            provider if provider is not None else get_reasoning_provider(request.provider_name)
        )
        expected_type = ARTIFACT_TYPE_FOR_VERB[request.verb]

        started_at = datetime.now(timezone.utc)
        clock_start = time.monotonic()

        status = "failed"
        failure_category: str | None = None
        failure_reason: str | None = None
        artifact: ReasoningArtifact | None = None

        verb_method = getattr(resolved_provider, request.verb, None)
        if verb_method is None:
            failure_category = "provider_unavailable"
            failure_reason = f"provider {resolved_provider.name!r} has no {request.verb!r} verb"
        else:
            try:
                raw = verb_method(request)
            except ReasoningProviderError as exc:
                failure_reason = str(exc)[:2000]
                failure_category = (
                    "provider_disabled"
                    if getattr(resolved_provider, "name", "") == "disabled"
                    else "provider_unauthorized"
                )
            except Exception as exc:  # a misbehaving provider must not crash the caller
                failure_reason = f"{type(exc).__name__}: {exc}"[:2000]
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
                        failure_reason = str(exc)[:2000]
                    else:
                        # isinstance(raw, expected_type) already proved raw is one of the three
                        # known artifact subtypes; expected_type's static type (type[_StrictArtifact])
                        # is just too coarse for mypy to narrow ReasoningArtifact from.
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
            },
        )

        invocation = await self.store.record_invocation(
            {
                "project_id": request.project_id,
                "thread_id": request.thread_id,
                "requested_by_principal_id": request.requested_by_principal_id,
                "reasoning_verb": request.verb,
                "requested_provider_name": request.provider_name or resolved_provider.name,
                "provider_mode": resolved_provider.mode,
                "model_name": request.model_name,
                "round_number": request.round_number,
                "status": status,
                "failure_category": failure_category,
                "failure_reason": failure_reason,
                "latency_ms": latency_ms,
                "correlation_id": request.correlation_id,
                "audit_ref": audit_ref,
                "started_at": started_at,
                "completed_at": completed_at,
            }
        )
        return ReasoningResult(artifact=artifact, invocation=invocation)


__all__ = ["ReasoningArtifact", "ReasoningResult", "ReasoningService"]
