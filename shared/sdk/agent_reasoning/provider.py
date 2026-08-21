"""Step AT-M3.1 -- reasoning provider protocol and factory.

Two provider modes ship in this slice:

* ``mock`` -- deterministic in-process generator. Default.
* ``disabled`` -- every call raises.

Every OTHER name -- including every ``external_*`` name a future slice might reserve -- also
refuses, via the exact same refusing implementation ``disabled`` uses. AT-M3.1 ships no live
adapter and opens no socket, so there is no name this factory can resolve to a network call; an
unrecognised or not-yet-authorised name is refused rather than silently treated as ``mock``.

This module deliberately does NOT repeat the one behaviour ``shared/sdk/llm/provider.py``'s
``ExternalLLMProviderGuard`` has: falling back to a mock-authored response (with confidence capped
and a note appended) when a real call is refused. That fallback would let a refused or
misconfigured live reasoning request be recorded as an ordinary team proposal, indistinguishable
from one a model actually produced. A refusal here always raises; it is never downgraded into a
result.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from shared.sdk.agent_reasoning.models import (
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ProposalArtifact,
    ReasoningRequest,
)

#: Default provider name when nothing is set. Must never be overridden to anything that reaches a
#: network without an opt-in flow -- and in this slice, nothing can, because no such adapter exists
#: yet.
DEFAULT_REASONING_PROVIDER = "mock"


class ReasoningProviderError(RuntimeError):
    """Raised when a reasoning provider refuses to satisfy a request."""


@runtime_checkable
class ReasoningProvider(Protocol):
    """Common provider interface for the three reasoning verbs."""

    name: str
    mode: str

    def propose(self, request: ReasoningRequest) -> ProposalArtifact: ...

    def critique(self, request: ReasoningRequest) -> CritiqueArtifact: ...

    def summarize_decision(self, request: ReasoningRequest) -> DecisionSummaryArtifact: ...


class DisabledReasoningProvider:
    """Refuses every call.

    Used both for an explicit operator choice of ``disabled`` and for any name this slice does not
    implement. ``name`` records what was actually asked for, so a refusal for
    ``external_anthropic`` is distinguishable in the audit trail from an explicit ``disabled``,
    even though both refuse identically and both persist ``provider_mode='disabled'``.
    """

    mode: str = "disabled"

    def __init__(self, requested_name: str = "disabled") -> None:
        self.name = requested_name or "disabled"

    def _refuse(self, verb: str) -> None:
        raise ReasoningProviderError(f"reasoning_provider_refused:{self.name}:{verb}")

    def propose(self, request: ReasoningRequest) -> ProposalArtifact:
        self._refuse("propose")
        raise ReasoningProviderError("unreachable")  # pragma: no cover

    def critique(self, request: ReasoningRequest) -> CritiqueArtifact:
        self._refuse("critique")
        raise ReasoningProviderError("unreachable")  # pragma: no cover

    def summarize_decision(self, request: ReasoningRequest) -> DecisionSummaryArtifact:
        self._refuse("summarize_decision")
        raise ReasoningProviderError("unreachable")  # pragma: no cover


def get_reasoning_provider(name: str | None = None) -> ReasoningProvider:
    """Factory. Anything other than ``mock`` refuses -- never silently interpreted as ``mock``.

    The raw requested name is preserved on the refusing provider even when unrecognised, so a
    misconfigured ``REASONING_PROVIDER`` env var is visible in the invocation record rather than
    swallowed into a generic ``disabled``.
    """
    from shared.sdk.agent_reasoning.mock_provider import MockReasoningProvider

    raw = (
        (name or os.environ.get("REASONING_PROVIDER") or DEFAULT_REASONING_PROVIDER).strip().lower()
    )
    if raw == "mock":
        return MockReasoningProvider()
    return DisabledReasoningProvider(requested_name=raw or "disabled")


__all__ = [
    "DEFAULT_REASONING_PROVIDER",
    "DisabledReasoningProvider",
    "ReasoningProvider",
    "ReasoningProviderError",
    "get_reasoning_provider",
]
