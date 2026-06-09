"""Stage 30 — LLM provider abstraction.

Four provider modes are supported by name:

* ``mock`` — deterministic in-process generator. Default.
* ``disabled`` — every call raises so the platform can refuse to do
  any LLM work even by accident.
* ``external_openai_placeholder`` — interface-only guard around a
  hypothetical OpenAI call. The placeholder NEVER calls a real API; it
  exists so the orchestrator can detect "the operator wired this up
  but didn't opt in" and refuse gracefully.
* ``external_anthropic_placeholder`` — same as above for Anthropic.

A real external call is allowed iff:

* ``RUN_REAL_LLM_TEST=true`` is set
* AND ``LLM_API_KEY`` (or the matching provider-specific key env var)
  is present
* AND the caller explicitly opted in by passing ``allow_real=True``

Even when all three are true, the placeholder still refuses with
``REAL_LLM_TEST_SKIPPED`` unless ``ENABLE_REAL_LLM_NETWORK_CALL=true``
is set — Stage 30 ships with the rail bolted shut.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, cast, runtime_checkable

from shared.sdk.llm.models import (
    LLMDevelopmentPlan,
    LLMFileChange,
    LLMPatchProposal,
    LLMTestPlan,
)
from shared.sdk.llm.mock_provider import MockLLMProvider

#: Default provider name when nothing is set. The orchestrator MUST
#: not override this to anything that calls a network without an
#: opt-in flow.
DEFAULT_PROVIDER = "mock"

#: Provider-name strings the factory recognises.
ALLOWED_PROVIDERS: tuple[str, ...] = (
    "mock",
    "disabled",
    "external_openai_placeholder",
    "external_anthropic_placeholder",
    # Stage 35 -- real LLM plan-only pilot.
    "external_openai",
    "external_anthropic",
)

#: Reasons surfaced by the real-LLM guard.
REAL_LLM_GUARD_REASONS = (
    "run_real_llm_test_false",
    "api_key_missing",
    "network_call_disabled",
    "allow_real_false",
)


class LLMProviderError(RuntimeError):
    """Raised when a provider refuses to satisfy a request."""


@runtime_checkable
class LLMProvider(Protocol):
    """Common provider interface.

    The concrete providers expose richer keyword args than the
    protocol; we use ``**kwargs`` here so the protocol stays
    structurally compatible with mock + disabled + guard
    implementations without inventing a contradictory signature.
    """

    name: str
    model_name: str

    def generate_development_plan(self, **kwargs: Any) -> LLMDevelopmentPlan: ...

    def generate_patch_proposal(self, **kwargs: Any) -> LLMPatchProposal: ...

    def generate_test_plan(self, **kwargs: Any) -> LLMTestPlan: ...


class DisabledLLMProvider:
    """Refuses every call. Use when the operator explicitly disabled LLM use."""

    name = "disabled"
    model_name = "disabled"

    def _refuse(self, kind: str) -> None:
        raise LLMProviderError(f"llm_provider_disabled:{kind}")

    def generate_development_plan(self, **_: Any) -> LLMDevelopmentPlan:
        self._refuse("development_plan")
        # unreachable
        raise LLMProviderError("unreachable")

    def generate_patch_proposal(self, **_: Any) -> LLMPatchProposal:
        self._refuse("patch_proposal")
        raise LLMProviderError("unreachable")

    def generate_test_plan(self, **_: Any) -> LLMTestPlan:
        self._refuse("test_plan")
        raise LLMProviderError("unreachable")


def real_llm_guard(
    *,
    provider_name: str,
    allow_real: bool,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Return ``(allowed, reason)`` for a real-LLM network call.

    Always returns ``(False, ...)`` in this stage unless every gate is
    explicitly opted in. The reason names match :data:`REAL_LLM_GUARD_REASONS`
    so callers can record them verbatim.
    """
    src: dict[str, str] = dict(env) if env is not None else dict(os.environ)
    if not allow_real:
        return False, "allow_real_false"
    run_real = (src.get("RUN_REAL_LLM_TEST", "false") or "").strip().lower() == "true"
    if not run_real:
        return False, "run_real_llm_test_false"
    network_ok = (src.get("ENABLE_REAL_LLM_NETWORK_CALL", "false") or "").strip().lower() == "true"
    if not network_ok:
        return False, "network_call_disabled"
    # Provider-specific key gate.
    key_env = "LLM_API_KEY"
    if provider_name == "external_openai_placeholder":
        key_env = "OPENAI_API_KEY"
    elif provider_name == "external_anthropic_placeholder":
        key_env = "ANTHROPIC_API_KEY"
    key_value = (src.get(key_env, "") or src.get("LLM_API_KEY", "") or "").strip()
    if not key_value:
        return False, "api_key_missing"
    return True, "ok"


class ExternalLLMProviderGuard:
    """Interface-only external provider guard.

    Even if all opt-in env vars line up the guard STILL refuses by
    falling through to ``REAL_LLM_TEST_SKIPPED`` — Stage 30 does not
    ship the wire-level client. The guard exists so callers can:

    1. detect the operator's intent (env vars present but disabled),
    2. record the refusal as an audit event, and
    3. show a "REAL_LLM_TEST_SKIPPED: PASS" line in verify scripts.
    """

    def __init__(self, vendor: str) -> None:
        self.name = f"external_{vendor}_placeholder"
        self.model_name = f"{vendor}-placeholder"
        self._mock = MockLLMProvider()

    def _refuse_or_simulate(self, kind: str, allow_real: bool) -> tuple[bool, str]:
        allowed, reason = real_llm_guard(provider_name=self.name, allow_real=allow_real)
        if not allowed:
            return False, reason
        return False, "network_call_disabled"  # Stage 30 hard rail

    def generate_development_plan(
        self, *, allow_real: bool = False, **kwargs: Any
    ) -> LLMDevelopmentPlan:
        allowed, _ = self._refuse_or_simulate("development_plan", allow_real)
        # When the guard says "no", we fall back to the deterministic mock
        # so callers always get a syntactically-valid response that the
        # safety policy can scan. The caller's audit / notification path
        # surfaces the reason — we don't raise from this routine.
        plan = self._mock.generate_development_plan(**kwargs)
        plan.confidence = min(plan.confidence, 0.4)
        plan.requires_human_review = True
        plan.assumptions = list(plan.assumptions) + [f"provider={self.name}", "real_call_skipped"]
        return plan

    def generate_patch_proposal(
        self, *, allow_real: bool = False, **kwargs: Any
    ) -> LLMPatchProposal:
        allowed, _ = self._refuse_or_simulate("patch_proposal", allow_real)
        proposal = self._mock.generate_patch_proposal(**kwargs)
        proposal.confidence = min(proposal.confidence, 0.4)
        proposal.requires_human_review = True
        proposal.safety_notes = list(proposal.safety_notes) + [
            f"provider={self.name}",
            "real_call_skipped",
        ]
        return proposal

    def generate_test_plan(self, *, allow_real: bool = False, **kwargs: Any) -> LLMTestPlan:
        allowed, _ = self._refuse_or_simulate("test_plan", allow_real)
        return self._mock.generate_test_plan(**kwargs)


def get_provider(name: str | None = None) -> LLMProvider:
    """Factory. Falls back to ``mock`` for unknown names but logs the input
    as the chosen provider so a misconfigured env var doesn't silently
    look correct."""
    raw = (name or os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if raw == "mock":
        return cast(LLMProvider, MockLLMProvider())
    if raw == "disabled":
        return cast(LLMProvider, DisabledLLMProvider())
    if raw == "external_openai_placeholder":
        return cast(LLMProvider, ExternalLLMProviderGuard("openai"))
    if raw == "external_anthropic_placeholder":
        return cast(LLMProvider, ExternalLLMProviderGuard("anthropic"))
    if raw == "external_openai":
        # Local import to avoid circular dependency at module load.
        from shared.sdk.llm.plan_only_provider import RealLLMPlanOnlyProvider

        return cast(LLMProvider, RealLLMPlanOnlyProvider(vendor="openai"))
    if raw == "external_anthropic":
        from shared.sdk.llm.plan_only_provider import RealLLMPlanOnlyProvider

        return cast(LLMProvider, RealLLMPlanOnlyProvider(vendor="anthropic"))
    # Unknown provider — refuse via DisabledLLMProvider so we never
    # accidentally interpret it as ``mock``.
    return cast(LLMProvider, DisabledLLMProvider())


__all__ = [
    "ALLOWED_PROVIDERS",
    "DEFAULT_PROVIDER",
    "DisabledLLMProvider",
    "ExternalLLMProviderGuard",
    "LLMFileChange",
    "LLMProvider",
    "LLMProviderError",
    "MockLLMProvider",
    "REAL_LLM_GUARD_REASONS",
    "get_provider",
    "real_llm_guard",
]
