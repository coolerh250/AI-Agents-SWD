"""Step AT-M3.1 -- reasoning contract: requests, structured artifacts, invocation metadata.

Vendor-neutral. Nothing here imports an SDK, opens a socket, or knows what an "OpenAI message" or
an "Anthropic content block" looks like -- that stays confined to a future live-provider adapter
(AT-M3.6+), which this module does not implement.

Artifacts hold conclusions a principal could stand behind, never the process that produced them --
the same line AT-M2 drew for ``TeamMessage`` (AT-D03 R8 / INV-04). ``extra="forbid"`` on every
artifact means a provider cannot smuggle an extra field (a ``chain_of_thought`` key, for instance)
into a structured response at all: an unexpected key is a validation error, not a stored column.
The dict-based marker scan AT-M2 already enforces on free-form JSONB content
(:func:`shared.sdk.agent_team.models.assert_content_is_safe`) is reused here rather than
duplicated, both on the resolved artifact and on the raw provider output before it is parsed.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shared.sdk.agent_team.models import assert_content_is_safe

ReasoningVerb = Literal["propose", "critique", "summarize_decision"]
REASONING_VERBS: tuple[str, ...] = ("propose", "critique", "summarize_decision")

# The provider CLASSES this slice implements. A future live adapter adds new modes; it never
# repurposes these two to mean something else (migration 037's CHECK constraint enforces this at
# the database layer too).
ProviderMode = Literal["mock", "disabled"]
PROVIDER_MODES: tuple[str, ...] = ("mock", "disabled")

InvocationStatus = Literal["succeeded", "failed"]

FailureCategory = Literal[
    "provider_disabled",
    "provider_unauthorized",
    "malformed_output",
    "content_safety_rejected",
    "provider_unavailable",
]
FAILURE_CATEGORIES: tuple[str, ...] = (
    "provider_disabled",
    "provider_unauthorized",
    "malformed_output",
    "content_safety_rejected",
    "provider_unavailable",
)


class _StrictArtifact(BaseModel):
    """Base for every structured reasoning artifact. No unknown field is ever accepted."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    rationale_summary: str = Field(min_length=1, max_length=2000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    def as_safe_dict(self) -> dict[str, Any]:
        """The artifact as a plain dict, after the same content-safety check TeamMessage uses.

        Raises exactly as :func:`assert_content_is_safe` does -- a rejection, never a scrub.
        """
        payload = self.model_dump(mode="json")
        assert_content_is_safe(payload, field=f"{type(self).__name__}.as_safe_dict")
        return payload


class ProposalArtifact(_StrictArtifact):
    """What ``propose`` returns: an option, its rationale, and what it does NOT resolve."""

    assumptions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    recommendation: str = Field(min_length=1, max_length=1000)


class CritiqueArtifact(_StrictArtifact):
    """What ``critique`` returns: an objection or endorsement of a standing proposal."""

    concerns: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    recommendation: str = Field(min_length=1, max_length=1000)


class DecisionSummaryArtifact(_StrictArtifact):
    """What ``summarize_decision`` returns.

    Shaped to feed a future ``TeamDecision`` (AT-M3.3+) without being one: this artifact is a
    reasoning OUTPUT, not a durable team coordination record, and recording it is not itself an
    act of deciding.
    """

    options_considered: tuple[str, ...] = Field(min_length=1)
    selected_option: str = Field(min_length=1, max_length=500)
    dissent_summary: str | None = Field(default=None, max_length=2000)


ARTIFACT_TYPE_FOR_VERB: dict[str, type[_StrictArtifact]] = {
    "propose": ProposalArtifact,
    "critique": CritiqueArtifact,
    "summarize_decision": DecisionSummaryArtifact,
}


class ReasoningRequest(BaseModel):
    """One reasoning call's INPUT. Never persisted verbatim -- see ``ReasoningInvocation``.

    ``context`` is the caller's free-form input (a goal statement, a work-item summary, a standing
    proposal to critique, ...). It is passed to the provider in memory and is never written to
    durable storage by this module; a provider MAY echo redacted fragments of it into a returned
    artifact's ``summary``/``rationale_summary``, which then goes through the same content-safety
    check as everything else.
    """

    verb: ReasoningVerb
    context: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    thread_id: str | None = None
    requested_by_principal_id: str | None = None
    round_number: int = Field(default=1, ge=1)
    provider_name: str | None = None
    model_name: str | None = None
    # Supplied by the caller so a retried call can be recognised as a replay rather than a new
    # attempt. The service generates one when the caller does not supply it.
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))

    @model_validator(mode="after")
    def _context_carries_no_hidden_reasoning(self) -> "ReasoningRequest":
        # Mirrors TeamMessageCreate._must_be_addressed's use of the same helper: a request whose
        # context already carries a chain_of_thought/secret-shaped key is rejected at
        # construction, before any provider is ever called with it.
        assert_content_is_safe(self.context, "context")
        return self


class ReasoningInvocation(BaseModel):
    """The durable METADATA record of one reasoning call. Mirrors ``reasoning_invocations``.

    Never carries a prompt, a completion, hidden reasoning or a credential (AT-D03 R8 / INV-04,
    restated for AT-M3). ``mode`` is the field a caller checks before trusting a result: a `mock`
    invocation must never be mistaken for a `live` one because no third mode exists yet to confuse
    it with.
    """

    invocation_id: UUID
    project_id: UUID | None = None
    thread_id: UUID | None = None
    requested_by_principal_id: UUID | None = None
    reasoning_verb: ReasoningVerb
    requested_provider_name: str = Field(min_length=1, max_length=100)
    provider_mode: ProviderMode
    model_name: str | None = None
    round_number: int = Field(default=1, ge=1)
    status: InvocationStatus
    failure_category: FailureCategory | None = None
    failure_reason: str | None = Field(default=None, max_length=2000)
    outcome_ref: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int | None = None
    correlation_id: UUID
    audit_ref: str | None = None
    started_at: Any = None
    completed_at: Any = None
    created_at: Any = None


__all__ = [
    "ARTIFACT_TYPE_FOR_VERB",
    "CritiqueArtifact",
    "DecisionSummaryArtifact",
    "FAILURE_CATEGORIES",
    "FailureCategory",
    "InvocationStatus",
    "PROVIDER_MODES",
    "ProposalArtifact",
    "ProviderMode",
    "REASONING_VERBS",
    "ReasoningInvocation",
    "ReasoningRequest",
    "ReasoningVerb",
]
