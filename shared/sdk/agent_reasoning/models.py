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

import json
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

# The provider CLASSES the runtime implements. AT-M3.6B.1 adds the third and last one this
# architecture needs. A mode is a CLASS of provider, never a vendor: `live` means "a real external
# model answered", and WHICH model answered is `model_name`, not the mode. That separation is why
# adding Anthropic did not add `anthropic_live` -- a vendor-shaped mode would have to be widened
# again for every vendor, and every reader of `provider_mode` would have to learn the vendor list
# to answer the only question the column exists for: was this real?
#
# migration 037 constrained this to ('mock','disabled') and migration 044 widens it to admit
# 'live'. Neither of the original two is repurposed.
ProviderMode = Literal["mock", "disabled", "live"]
PROVIDER_MODES: tuple[str, ...] = ("mock", "disabled", "live")

#: The one mode in which a real external provider is contacted. Named once, here, so no module has
#: to spell the string to ask the question.
PROVIDER_MODE_LIVE = "live"

# started: durably claimed, no terminal outcome yet. succeeded/failed: terminal, reachable only
# from started (shared/sdk/agent_reasoning/store.py::complete_invocation guards the transition).
InvocationStatus = Literal["started", "succeeded", "failed"]
INVOCATION_STATUSES: tuple[str, ...] = ("started", "succeeded", "failed")

# AT-M3.6B.1 adds exactly three. The five AT-M3.1 categories already cover most of the live
# taxonomy and are reused rather than duplicated under new names: an invalid credential is
# `provider_unauthorized`, an outage or connection reset is `provider_unavailable`, output that
# does not parse or does not validate is `malformed_output`, and a forbidden-key artifact is
# `content_safety_rejected`. What genuinely could not be said before is a call that ran out of
# time, a call the provider rate-limited, and a call that was refused because it would have cost
# too much -- the first two are retryable and the third is terminal, so collapsing any of them
# into `provider_unavailable` would have made retryability underivable.
#
# No Anthropic-specific category exists. A vendor's HTTP status codes and error bodies are
# implementation detail; the canonical taxonomy is what a caller reasons about.
FailureCategory = Literal[
    "provider_disabled",
    "provider_unauthorized",
    "malformed_output",
    "content_safety_rejected",
    "provider_unavailable",
    "provider_timeout",
    "rate_limited",
    "budget_exceeded",
]
FAILURE_CATEGORIES: tuple[str, ...] = (
    "provider_disabled",
    "provider_unauthorized",
    "malformed_output",
    "content_safety_rejected",
    "provider_unavailable",
    "provider_timeout",
    "rate_limited",
    "budget_exceeded",
)

#: Categories a later attempt may reasonably re-try, because the failure was about the moment
#: rather than about the request. Everything else is deterministic given the same input and
#: re-attempting it would spend money to fail identically.
RETRYABLE_FAILURE_CATEGORIES: frozenset[str] = frozenset(
    {"provider_timeout", "rate_limited", "provider_unavailable"}
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


#: The maximum serialized size of ONE durable reasoning artifact, in bytes (256 KiB).
#:
#: AT-D23 section 6 recorded the absence of this bound as PRE-M3.6B backlog, and AT-M3.6B.1 is the
#: slice that makes it load-bearing: until now every artifact was authored by a deterministic
#: in-process mock, so the column's content was trusted by construction. A real external model's
#: output is not.
#:
#: This is a BACKSTOP, not the binding constraint. The per-verb output token cap
#: (shared/sdk/agent_reasoning/live_config.py) tops out at 4000 tokens for decompose_plan, which
#: is on the order of 16 KB of text -- an order of magnitude below this bound. What the byte cap
#: catches is the case the token cap cannot: a provider that ignores max_tokens entirely. The two
#: controls fail independently and neither substitutes for the other.
MAX_ARTIFACT_BYTES = 256 * 1024


def serialize_artifact_payload(payload: dict[str, Any]) -> bytes:
    """The exact bytes an artifact's size is measured in.

    Deterministic (sorted keys, no incidental whitespace) so the measurement is a property of the
    artifact rather than of who serialized it. Not the bytes PostgreSQL stores -- JSONB has its own
    representation -- but a stable, reproducible proxy that every caller agrees on.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def artifact_payload_size(payload: dict[str, Any]) -> int:
    """Serialized size of an artifact payload, in bytes."""
    return len(serialize_artifact_payload(payload))


def assert_artifact_within_size(
    payload: dict[str, Any], *, limit: int = MAX_ARTIFACT_BYTES, field: str = "artifact"
) -> None:
    """Raise when a validated artifact is larger than the durable bound.

    Checked BEFORE the terminal write, never after: an oversized artifact must not become a
    SUCCEEDED row and then be discovered. Like :func:`assert_content_is_safe` this rejects rather
    than truncating -- half an artifact is not a smaller artifact, it is a corrupt one.
    """
    size = artifact_payload_size(payload)
    if size > limit:
        raise ValueError(
            f"{field} is {size} bytes, which exceeds the durable maximum of {limit} bytes"
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
    """The durable record of one reasoning call. Mirrors ``reasoning_invocations``.

    Never carries a prompt, a completion, hidden reasoning or a credential (AT-D03 R8 / INV-04,
    restated for AT-M3). ``provider_mode`` is the field a caller checks before trusting a result: a
    `mock` invocation must never be mistaken for a `live` one because no third mode exists yet to
    confuse it with.

    ``status='started'`` is durable evidence that a call was claimed, written BEFORE the provider
    ever runs. It is never itself a claim of success or failure -- only ``succeeded``/``failed``
    are terminal, and only one of them is ever reachable from a given row.

    AT-M3.4 (rebaselined) added the durable ``artifact``. This row used to be metadata ONLY, which
    meant a succeeded call whose caller crashed before using the result left the outcome terminal
    and the result unrecoverable -- permanently, since a terminal correlation_id is never
    re-invoked. ``succeeded`` now carries the safe artifact that produced it, written by the same
    UPDATE, so replay can return the real thing instead of ``None``. What is stored is exactly
    what a TeamMessage already stores: a closed-schema, content-screened business artifact.
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
    #: The artifact class this row's ``artifact`` should be rebuilt through. Agrees with
    #: ``reasoning_verb`` by database constraint, so the two can never disagree about what is
    #: stored here.
    artifact_type: str | None = None
    #: The RECOVERY COPY of the validated safe artifact (``_StrictArtifact.as_safe_dict()``),
    #: written by the same UPDATE that made this row terminal. Present on every succeeded row
    #: written under the AT-M3.4 contract; absent only on a legacy row that predates it.
    #: It is not a second product authority -- the artifact the team can see is the TeamMessage.
    artifact: dict[str, Any] | None = None
    #: 1 for the original claim, incremented once per takeover of an expired lease. Truthfully
    #: records how many times a provider was actually asked for this correlation_id.
    attempt: int = Field(default=1, ge=1)
    #: The current attempt's owner. A worker whose lease was taken over cannot terminalize.
    attempt_token: UUID | None = None
    #: Database-clock ownership bound. NULL when terminal, or on a legacy pre-contract row.
    lease_expires_at: Any = None
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
    "MAX_ARTIFACT_BYTES",
    "PROVIDER_MODE_LIVE",
    "RETRYABLE_FAILURE_CATEGORIES",
    "artifact_payload_size",
    "assert_artifact_within_size",
    "serialize_artifact_payload",
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
