"""Step AT-M3.1 -- reasoning contract & provider abstraction. Extended by AT-M3.6B.1 (AT-D24).

Public surface for the reasoning foundation the bounded team-discussion loop (AT-M3.3) and the
planner (AT-M3.4) call. Three provider classes exist: the deterministic local
:class:`~shared.sdk.agent_reasoning.mock_provider.MockReasoningProvider` (the default), a refusing
provider, and -- as of AT-M3.6B.1 -- an Anthropic adapter that is resolvable ONLY from runtime
configuration and whose network gate defaults to closed. Importing this package still opens no
socket and pulls in no vendor SDK: the adapter is imported lazily by the factory, and only when the
environment names it.

Every invocation is claimed durably BEFORE the provider runs (:meth:`ReasoningService.invoke`), so
a caller must check :attr:`ReasoningResult.disposition` -- not only `.succeeded` -- before treating
`.artifact` as authoritative.
"""

from __future__ import annotations

from shared.sdk.agent_reasoning.models import (
    ARTIFACT_TYPE_FOR_VERB,
    EXECUTION_DISPOSITIONS,
    FAILURE_CATEGORIES,
    INVOCATION_STATUSES,
    MAX_ARTIFACT_BYTES,
    PROVIDER_MODE_LIVE,
    PROVIDER_MODES,
    REASONING_VERBS,
    RETRYABLE_FAILURE_CATEGORIES,
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ExecutionDisposition,
    FailureCategory,
    InvocationStatus,
    PlanDraftArtifact,
    ProposalArtifact,
    ProviderMode,
    ReasoningInvocation,
    ReasoningRequest,
    ReasoningVerb,
    artifact_payload_size,
    assert_artifact_within_size,
    sanitize_failure_reason,
)
from shared.sdk.agent_reasoning.provider import (
    DEFAULT_REASONING_PROVIDER,
    DisabledReasoningProvider,
    LiveProviderError,
    ProviderResult,
    ProviderUsage,
    ReasoningProvider,
    ReasoningProviderError,
    get_reasoning_provider,
)
from shared.sdk.agent_reasoning.service import (
    ReasoningArtifactCorruptError,
    ReasoningArtifact,
    ReasoningPersistenceError,
    ReasoningResult,
    ReasoningService,
)
from shared.sdk.agent_reasoning.store import ReasoningInvocationStore

__all__ = [
    "ARTIFACT_TYPE_FOR_VERB",
    "DEFAULT_REASONING_PROVIDER",
    "EXECUTION_DISPOSITIONS",
    "FAILURE_CATEGORIES",
    "INVOCATION_STATUSES",
    "MAX_ARTIFACT_BYTES",
    "PROVIDER_MODES",
    "PROVIDER_MODE_LIVE",
    "REASONING_VERBS",
    "RETRYABLE_FAILURE_CATEGORIES",
    "CritiqueArtifact",
    "DecisionSummaryArtifact",
    "DisabledReasoningProvider",
    "ExecutionDisposition",
    "FailureCategory",
    "InvocationStatus",
    "LiveProviderError",
    "PlanDraftArtifact",
    "ProposalArtifact",
    "ProviderMode",
    "ProviderResult",
    "ProviderUsage",
    "ReasoningArtifact",
    "ReasoningInvocation",
    "ReasoningInvocationStore",
    "ReasoningArtifactCorruptError",
    "ReasoningPersistenceError",
    "ReasoningProvider",
    "ReasoningProviderError",
    "ReasoningRequest",
    "ReasoningResult",
    "ReasoningService",
    "ReasoningVerb",
    "artifact_payload_size",
    "assert_artifact_within_size",
    "get_reasoning_provider",
    "sanitize_failure_reason",
]
