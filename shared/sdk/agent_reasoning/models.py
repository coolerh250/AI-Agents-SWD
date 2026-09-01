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

from shared.sdk.agent_planning.models import PlanContent
from shared.sdk.agent_team.models import FORBIDDEN_CONTENT_KEY_MARKERS, assert_content_is_safe
from shared.sdk.llm.prompt_contract import redact_text

ReasoningVerb = Literal["propose", "critique", "summarize_decision", "decompose_plan"]
REASONING_VERBS: tuple[str, ...] = (
    "propose",
    "critique",
    "summarize_decision",
    # AT-M3.4. The verb that gives AT-D14 section 2 -- "the planner producing a draft
    # PlanRevision's work items and dependencies from a Goal and a discussion outcome" -- a
    # runtime meaning. Until it existed, no verb produced a plan, so the plan had to come from
    # a caller, and a caller-supplied plan is not evidence of what the team chose.
    "decompose_plan",
)

# The provider CLASSES this slice implements. A future live adapter adds new modes; it never
# repurposes these two to mean something else (migration 037's CHECK constraint enforces this at
# the database layer too).
ProviderMode = Literal["mock", "disabled"]
PROVIDER_MODES: tuple[str, ...] = ("mock", "disabled")

# started: durably claimed, no terminal outcome yet. succeeded/failed: terminal, reachable only
# from started (shared/sdk/agent_reasoning/store.py::complete_invocation guards the transition).
InvocationStatus = Literal["started", "succeeded", "failed"]
INVOCATION_STATUSES: tuple[str, ...] = ("started", "succeeded", "failed")

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

# What a caller learns about EXECUTION PROVENANCE, distinct from status (the OUTCOME).
# fresh        this call's own provider invocation produced this outcome just now.
# replay       a duplicate correlation_id resolved to a PRIOR call's already-terminal row; no
#              provider was invoked by this caller, and no artifact is fabricated to match it.
# in_progress  a duplicate correlation_id resolved to a row still 'started'; the original caller
#              has not reached a terminal outcome yet. No provider was invoked by this caller.
ExecutionDisposition = Literal["fresh", "replay", "in_progress"]
EXECUTION_DISPOSITIONS: tuple[str, ...] = ("fresh", "replay", "in_progress")

# Substrings scanned (case-insensitively) against a candidate failure_reason. Reuses the EXISTING
# AT-M2 marker vocabulary (FORBIDDEN_CONTENT_KEY_MARKERS) rather than defining a second list --
# free text and dict keys are different shapes, but the prohibited vocabulary is the same one.
_FAILURE_REASON_MARKER_MATCH = tuple(m.lower() for m in FORBIDDEN_CONTENT_KEY_MARKERS)


def sanitize_failure_reason(raw: str | None, *, limit: int = 500) -> str | None:
    """A bounded, safe-by-construction summary for a free-text failure reason.

    Unlike :func:`assert_content_is_safe` (reject, never scrub -- appropriate for deliberately
    authored collaboration content), this function DEGRADES rather than raises: a failure_reason
    is diagnostic telemetry captured automatically from exception handling, not content a caller
    composed and could be asked to fix and resubmit. Trusting ``str(exception)`` verbatim is not
    safe -- a misbehaving or adversarial provider's exception can contain anything, including
    echoed wire content.

    1. Known credential-SHAPED patterns are redacted in place (reuses
       ``shared.sdk.llm.prompt_contract.redact_text`` -- the same helper the mock provider already
       uses for caller-supplied text).
    2. If a forbidden KEYWORD marker (chain_of_thought, raw_prompt, secret, credential, ...) is
       still present anywhere in the text after that, the entire reason is replaced with a generic,
       fully safe placeholder -- surgically redacting only the matched span would still require
       trusting the surrounding text, which is exactly what this function must not do.
    """
    if not raw:
        return None
    text = redact_text(raw, limit=limit)
    if any(marker in text.lower() for marker in _FAILURE_REASON_MARKER_MATCH):
        return "reason_redacted:forbidden_marker_detected"
    return text


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


class PlanDraftArtifact(_StrictArtifact):
    """What ``decompose_plan`` returns: a structured candidate plan, not prose about one.

    ``plan`` is AT-M3.2's own ``PlanContent``, reused verbatim rather than mirrored. That single
    choice is what makes the artifact usable as the plan a PlanRevision carries: step-key
    uniqueness, dependency existence, self-dependency and the forbidden-key screen are the
    validation M3.2 already performs, so a draft that parses here is a plan that can be stored
    there without a second schema disagreeing with the first.

    The artifact is a reasoning OUTPUT. Producing one decides nothing and accepts nothing -- the
    same separation ``DecisionSummaryArtifact`` keeps from ``TeamDecision``.
    """

    plan: PlanContent


ARTIFACT_TYPE_FOR_VERB: dict[str, type[_StrictArtifact]] = {
    "propose": ProposalArtifact,
    "critique": CritiqueArtifact,
    "summarize_decision": DecisionSummaryArtifact,
    "decompose_plan": PlanDraftArtifact,
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
    restated for AT-M3). ``provider_mode`` is the field a caller checks before trusting a result: a
    `mock` invocation must never be mistaken for a `live` one because no third mode exists yet to
    confuse it with.

    ``status='started'`` is durable evidence that a call was claimed, written BEFORE the provider
    ever runs. It is never itself a claim of success or failure -- only ``succeeded``/``failed``
    are terminal, and only one of them is ever reachable from a given row.
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
    "EXECUTION_DISPOSITIONS",
    "ExecutionDisposition",
    "CritiqueArtifact",
    "DecisionSummaryArtifact",
    "FAILURE_CATEGORIES",
    "FailureCategory",
    "INVOCATION_STATUSES",
    "InvocationStatus",
    "PROVIDER_MODES",
    "PlanDraftArtifact",
    "ProposalArtifact",
    "ProviderMode",
    "REASONING_VERBS",
    "ReasoningInvocation",
    "ReasoningRequest",
    "ReasoningVerb",
    "sanitize_failure_reason",
]
