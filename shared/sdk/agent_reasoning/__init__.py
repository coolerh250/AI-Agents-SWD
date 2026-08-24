"""Step AT-M3.1 -- reasoning contract & provider abstraction (AT-D14, mock/local only).

Public surface for the reasoning foundation a future bounded team-discussion loop (AT-M3.3) will
call. Nothing in this package makes a network call or depends on a vendor SDK; the only implemented
provider is deterministic and local (:class:`~shared.sdk.agent_reasoning.mock_provider.MockReasoningProvider`).

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
    PROVIDER_MODES,
    REASONING_VERBS,
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ExecutionDisposition,
    FailureCategory,
    InvocationStatus,
    ProposalArtifact,
    ProviderMode,
    ReasoningInvocation,
    ReasoningRequest,
    ReasoningVerb,
    sanitize_failure_reason,
)
from shared.sdk.agent_reasoning.provider import (
    DEFAULT_REASONING_PROVIDER,
    DisabledReasoningProvider,
    ReasoningProvider,
    ReasoningProviderError,
    get_reasoning_provider,
)
from shared.sdk.agent_reasoning.service import (
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
    "PROVIDER_MODES",
    "REASONING_VERBS",
    "CritiqueArtifact",
    "DecisionSummaryArtifact",
    "DisabledReasoningProvider",
    "ExecutionDisposition",
    "FailureCategory",
    "InvocationStatus",
    "ProposalArtifact",
    "ProviderMode",
    "ReasoningArtifact",
    "ReasoningInvocation",
    "ReasoningInvocationStore",
    "ReasoningPersistenceError",
    "ReasoningProvider",
    "ReasoningProviderError",
    "ReasoningRequest",
    "ReasoningResult",
    "ReasoningService",
    "ReasoningVerb",
    "get_reasoning_provider",
    "sanitize_failure_reason",
]
