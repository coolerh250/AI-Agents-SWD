"""Stage 30 — LLM-assisted development planning guardrails SDK.

Public surface:

* :class:`LLMDevelopmentPlan`, :class:`LLMPatchProposal`,
  :class:`LLMFileChange`, :class:`LLMTestPlan`,
  :class:`LLMInteraction`, :class:`LLMProposalArtifact`,
  :class:`LLMUsageRecord` — dataclass snapshots of Stage 30 schemas.
* :class:`LLMProvider`, :class:`MockLLMProvider`,
  :class:`DisabledLLMProvider`, :class:`ExternalLLMProviderGuard` —
  the provider abstraction.
* :func:`get_provider` — provider factory (mock by default).
* :func:`apply_llm_safety_policy`, :class:`LLMSafetyPolicy` —
  deterministic safety check on LLM output.
* :func:`build_prompt_contract`, :func:`hash_text`, :func:`redact_text`
  — prompt contract helpers.
* :class:`LLMInteractionStore` — async asyncpg store for the
  Stage 30 tables.
* Constants: ``DEFAULT_PROVIDER``, ``ALLOWED_PROVIDERS``,
  ``ALLOWED_CHANGE_TYPES``, ``REAL_LLM_GUARD_REASONS``.
"""

from shared.sdk.llm.models import (
    ALLOWED_CHANGE_TYPES,
    LLMDevelopmentPlan,
    LLMFileChange,
    LLMInteraction,
    LLMPatchProposal,
    LLMProposalArtifact,
    LLMTestPlan,
    LLMUsageRecord,
)
from shared.sdk.llm.policy import (
    DEFAULT_POLICY_LIMITS,
    LLMSafetyPolicy,
    apply_llm_safety_policy,
)
from shared.sdk.llm.prompt_contract import (
    PROMPT_CONTRACT_VERSION,
    build_prompt_contract,
    hash_text,
    redact_text,
)
from shared.sdk.llm.provider import (
    ALLOWED_PROVIDERS,
    DEFAULT_PROVIDER,
    REAL_LLM_GUARD_REASONS,
    DisabledLLMProvider,
    ExternalLLMProviderGuard,
    LLMProvider,
    MockLLMProvider,
    get_provider,
    real_llm_guard,
)
from shared.sdk.llm.store import LLMInteractionStore

__all__ = [
    "ALLOWED_CHANGE_TYPES",
    "ALLOWED_PROVIDERS",
    "DEFAULT_POLICY_LIMITS",
    "DEFAULT_PROVIDER",
    "DisabledLLMProvider",
    "ExternalLLMProviderGuard",
    "LLMDevelopmentPlan",
    "LLMFileChange",
    "LLMInteraction",
    "LLMInteractionStore",
    "LLMPatchProposal",
    "LLMProposalArtifact",
    "LLMProvider",
    "LLMSafetyPolicy",
    "LLMTestPlan",
    "LLMUsageRecord",
    "MockLLMProvider",
    "PROMPT_CONTRACT_VERSION",
    "REAL_LLM_GUARD_REASONS",
    "apply_llm_safety_policy",
    "build_prompt_contract",
    "get_provider",
    "hash_text",
    "real_llm_guard",
    "redact_text",
]
