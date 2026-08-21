"""Step AT-M3.1 -- reasoning contract & provider abstraction (AT-D14, mock/local only).

Public surface for the reasoning foundation a future bounded team-discussion loop (AT-M3.3) will
call. Nothing in this package makes a network call or depends on a vendor SDK; the only implemented
provider is deterministic and local (:class:`~shared.sdk.agent_reasoning.mock_provider.MockReasoningProvider`).
"""

from __future__ import annotations

from shared.sdk.agent_reasoning.models import (
    ARTIFACT_TYPE_FOR_VERB,
    FAILURE_CATEGORIES,
    PROVIDER_MODES,
    REASONING_VERBS,
    CritiqueArtifact,
    DecisionSummaryArtifact,
    FailureCategory,
    InvocationStatus,
    ProposalArtifact,
    ProviderMode,
    ReasoningInvocation,
    ReasoningRequest,
    ReasoningVerb,
)
from shared.sdk.agent_reasoning.provider import (
    DEFAULT_REASONING_PROVIDER,
    DisabledReasoningProvider,
    ReasoningProvider,
    ReasoningProviderError,
    get_reasoning_provider,
)
from shared.sdk.agent_reasoning.service import ReasoningArtifact, ReasoningResult, ReasoningService
from shared.sdk.agent_reasoning.store import ReasoningInvocationStore

__all__ = [
    "ARTIFACT_TYPE_FOR_VERB",
    "DEFAULT_REASONING_PROVIDER",
    "FAILURE_CATEGORIES",
    "PROVIDER_MODES",
    "REASONING_VERBS",
    "CritiqueArtifact",
    "DecisionSummaryArtifact",
    "DisabledReasoningProvider",
    "FailureCategory",
    "InvocationStatus",
    "ProposalArtifact",
    "ProviderMode",
    "ReasoningArtifact",
    "ReasoningInvocation",
    "ReasoningInvocationStore",
    "ReasoningProvider",
    "ReasoningProviderError",
    "ReasoningRequest",
    "ReasoningResult",
    "ReasoningService",
    "ReasoningVerb",
    "get_reasoning_provider",
]
