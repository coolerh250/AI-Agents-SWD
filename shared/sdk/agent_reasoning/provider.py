"""Step AT-M3.1 -- reasoning provider protocol and factory. Extended by AT-M3.6B.1.

Three provider modes now ship:

* ``mock`` -- deterministic in-process generator. Default.
* ``disabled`` -- every call raises.
* ``live`` -- a real external model, resolved ONLY from runtime configuration (AT-M3.6B.1).

Every OTHER name -- including every ``external_*`` name an older subsystem reserved -- still
refuses, via the exact same refusing implementation ``disabled`` uses. An unrecognised or
not-yet-authorised name is refused rather than silently treated as ``mock``.

THE LIVE PROVIDER IS NOT REACHABLE BY NAME. :func:`get_reasoning_provider` resolves the live adapter
from the environment and from nothing else. A caller passing ``provider_name="anthropic"`` into a
``ReasoningRequest`` gets the refusing provider, exactly as it would for any other unauthorized
name -- because ``provider_name`` is a record of what was ASKED FOR, and letting it choose the
provider would turn a request field into a route to paid inference against an arbitrary vendor.
Conversely, when the environment IS configured for live reasoning, a request cannot downgrade the
runtime to ``mock`` either: a caller must not be able to make a live deployment quietly produce
mock-authored results that are indistinguishable from real ones.

This module deliberately does NOT repeat the one behaviour ``shared/sdk/llm/provider.py``'s
``ExternalLLMProviderGuard`` has: falling back to a mock-authored response (with confidence capped
and a note appended) when a real call is refused. That fallback would let a refused or
misconfigured live reasoning request be recorded as an ordinary team proposal, indistinguishable
from one a model actually produced. A refusal here always raises; it is never downgraded into a
result, and AT-M3.6B.1 adds no fallback of any kind -- not to another model, not to another
provider, and not to the mock.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from shared.sdk.agent_reasoning.models import (
    ReasoningRequest,
)

#: Default provider name when nothing is set. Must never be overridden to anything that reaches a
#: network without an opt-in flow.
DEFAULT_REASONING_PROVIDER = "mock"


class ReasoningProviderError(RuntimeError):
    """Raised when a reasoning provider refuses to satisfy a request."""


@dataclass(frozen=True)
class ProviderUsage:
    """What a provider call actually consumed. Safe metadata only -- never content.

    Carried both on a successful :class:`ProviderResult` AND on a :class:`LiveProviderError`,
    because a call that reached the provider costs the same whether or not its output turned out to
    be usable. Dropping usage on a malformed response would make the audit trail cheaper than the
    invoice.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    #: The pre-flight ESTIMATE, which is what gated the spend. The ACTUAL cost lives in the
    #: llm_budget usage ledger, which is the existing canonical location for it.
    estimated_cost_usd: float | None = None
    #: The provider's own request identifier, when it returns a non-secret one. The only field that
    #: lets a disputed charge be traced back to a canonical invocation.
    provider_request_id: str | None = None
    model_name: str | None = None
    #: True when a request actually reached the provider. False for a refusal that never left.
    call_occurred: bool = False


@dataclass(frozen=True)
class ProviderResult:
    """An artifact plus the metadata of the call that produced it.

    Providers that have nothing to report -- the mock, and anything written against the AT-M3.1
    contract -- keep returning a bare artifact. ``ReasoningService`` accepts either shape, so this
    is an additive channel rather than a protocol break.
    """

    artifact: Any
    usage: ProviderUsage | None = None


class LiveProviderError(ReasoningProviderError):
    """A live provider refusal or failure that already knows its canonical failure category.

    ``ReasoningService`` maps a plain :class:`ReasoningProviderError` to a category by inspecting
    the provider, which was sufficient while the only refusals were "disabled" and "not authorized".
    A live path fails in ways that are genuinely different from one another -- timed out, rate
    limited, over budget, unauthorized, malformed -- and the difference decides whether a later
    attempt is worth making. Rather than have the service re-derive that from an exception message,
    which is untrusted text, the raiser states it.
    """

    def __init__(
        self,
        message: str,
        *,
        failure_category: str,
        usage: ProviderUsage | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_category = failure_category
        self.usage = usage


#: What a verb may hand back. AT-M3.1 providers return the artifact itself; AT-M3.6B.1 providers
#: return a :class:`ProviderResult` so usage can travel with it; a provider that performs real I/O
#: returns an awaitable of either. ``ReasoningService`` normalises all four shapes.
VerbReturn = Any


@runtime_checkable
class ReasoningProvider(Protocol):
    """Common provider interface for the four reasoning verbs.

    THE VERBS MAY BE SYNCHRONOUS OR ASYNCHRONOUS. AT-M3.1 declared them synchronous because an
    in-process generator has no reason to await anything. A real provider does: a blocking HTTP call
    inside an ``async def`` stops the orchestrator's whole event loop for the duration of the
    request timeout, which would let one slow reasoning call freeze every other request the process
    is serving. So a verb may return its artifact directly, or return an awaitable of it, and
    ``ReasoningService`` awaits whatever it gets. Existing synchronous providers are unaffected --
    this widens what is accepted rather than changing what is required.
    """

    name: str
    mode: str

    def propose(self, request: ReasoningRequest) -> VerbReturn: ...

    def critique(self, request: ReasoningRequest) -> VerbReturn: ...

    def summarize_decision(self, request: ReasoningRequest) -> VerbReturn: ...

    def decompose_plan(self, request: ReasoningRequest) -> VerbReturn: ...


class DisabledReasoningProvider:
    """Refuses every call.

    Used both for an explicit operator choice of ``disabled`` and for any name this runtime does not
    implement. ``name`` records what was actually asked for, so a refusal for ``external_anthropic``
    is distinguishable in the audit trail from an explicit ``disabled``, even though both refuse
    identically and both persist ``provider_mode='disabled'``.
    """

    mode: str = "disabled"

    def __init__(self, requested_name: str = "disabled") -> None:
        self.name = requested_name or "disabled"

    def _refuse(self, verb: str) -> None:
        raise ReasoningProviderError(f"reasoning_provider_refused:{self.name}:{verb}")

    def propose(self, request: ReasoningRequest) -> VerbReturn:
        self._refuse("propose")
        raise ReasoningProviderError("unreachable")  # pragma: no cover

    def critique(self, request: ReasoningRequest) -> VerbReturn:
        self._refuse("critique")
        raise ReasoningProviderError("unreachable")  # pragma: no cover

    def summarize_decision(self, request: ReasoningRequest) -> VerbReturn:
        self._refuse("summarize_decision")
        raise ReasoningProviderError("unreachable")  # pragma: no cover

    def decompose_plan(self, request: ReasoningRequest) -> VerbReturn:
        self._refuse("decompose_plan")
        raise ReasoningProviderError("unreachable")  # pragma: no cover


def get_reasoning_provider(name: str | None = None) -> ReasoningProvider:
    """Factory. Anything other than ``mock`` refuses -- never silently interpreted as ``mock``.

    The ENVIRONMENT decides first, and it is the only thing that can select the live adapter. When
    ``REASONING_PROVIDER`` names the authorized live provider, that adapter is returned regardless
    of what ``name`` says: a caller may neither route itself to a live model nor route a live
    runtime back down to the mock. Otherwise the caller-supplied name is honoured for the two
    in-process modes, and every unrecognised name is refused with the raw requested name preserved
    on the refusing provider, so a misconfigured env var is visible in the invocation record rather
    than swallowed into a generic ``disabled``.
    """
    from shared.sdk.agent_reasoning.live_config import LIVE_PROVIDER_NAME
    from shared.sdk.agent_reasoning.mock_provider import MockReasoningProvider

    configured = (os.environ.get("REASONING_PROVIDER") or "").strip().lower()
    if configured == LIVE_PROVIDER_NAME:
        from shared.sdk.agent_reasoning.anthropic_provider import AnthropicReasoningProvider

        return AnthropicReasoningProvider()

    raw = (name or configured or DEFAULT_REASONING_PROVIDER).strip().lower()
    if raw == "mock":
        return MockReasoningProvider()
    return DisabledReasoningProvider(requested_name=raw or "disabled")


__all__ = [
    "DEFAULT_REASONING_PROVIDER",
    "DisabledReasoningProvider",
    "LiveProviderError",
    "ProviderResult",
    "ProviderUsage",
    "ReasoningProvider",
    "ReasoningProviderError",
    "VerbReturn",
    "get_reasoning_provider",
]
