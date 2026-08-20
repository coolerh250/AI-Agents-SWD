"""Step AT-M2-TEAM-CORE -- runtime team domain models.

These are the AT-M1 L2 collaboration entities made real. Names follow the canonical contracts
(actor-principal-and-team-model.md, collaboration-and-workroom-model.md) exactly; no parallel
identity or team model is introduced.

INV-04 (AT-D03 R8): no model here carries hidden reasoning. Durable fields hold conclusions a
principal stands behind -- summary, content, rationale_summary, dissent_summary, reason -- never
the process that produced them, and never a credential value.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

PrincipalType = Literal["human", "runtime_agent", "ai_partner", "system"]
PrincipalStatus = Literal["active", "suspended", "retired"]
ProfileStatus = Literal["active", "disabled", "retired"]
MembershipState = Literal["invited", "active", "paused", "left"]
ThreadType = Literal[
    "planning", "design", "execution", "debug", "blocker", "clarification", "handoff", "decision"
]
ThreadState = Literal["open", "resolved", "superseded", "archived"]
MessageType = Literal[
    "message",
    "proposal",
    "challenge",
    "decision_summary",
    "handoff",
    "blocker",
    "clarification_question",
    "clarification_answer",
    "debug_hypothesis",
    "debug_result",
    "replan",
    "system_event",
    "audit_event",
]
HandoffState = Literal["offered", "accepted", "declined", "withdrawn", "expired"]
RoutingOutcome = Literal["selected", "no_eligible_agent", "requires_human_approval"]

# clarification_answer is HUMAN-ONLY: an agent answering its own clarification would make the
# clarification loop decorative (collaboration-and-workroom-model.md section 5).
HUMAN_ONLY_MESSAGE_TYPES = frozenset({"clarification_answer"})
SYSTEM_ONLY_MESSAGE_TYPES = frozenset({"system_event", "audit_event"})

# AT-D03 R8 / INV-04, enforced on the PAYLOAD rather than only on the schema.
#
# No column in migration 036 is named for hidden reasoning, which satisfies the structural half
# of the prohibition. It does not satisfy the other half: ``content`` is free-form JSONB, so
# without this an agent could put a chain of thought or an API key inside it and the database
# would accept it happily. The contract says content is "structured body per message_type,
# REDACTED"; this is what makes that word mean something at runtime.
#
# Matched as substrings against KEY NAMES at any depth, so ``meta.private_chain_of_thought`` and
# ``ctx[0].api_key`` are caught as readily as a top-level key.
FORBIDDEN_CONTENT_KEY_MARKERS = (
    "chain_of_thought",
    "raw_reasoning",
    "hidden_reasoning",
    "reasoning_token",
    "token_trace",
    "scratchpad",
    "system_prompt",
    "raw_prompt",
    "unredacted",
    "api_key",
    "apikey",
    "secret",
    "credential",
    "password",
    "passphrase",
    "private_key",
    "access_key",
    "token",
)

# Keys whose NAME contains a forbidden marker but which are established, safe references used
# elsewhere in this domain. Kept explicit and tiny: an allowlist that grows without argument is
# how a prohibition dies.
ALLOWED_CONTENT_KEY_EXCEPTIONS = frozenset({"token_budget"})

_MAX_CONTENT_DEPTH = 12


def forbidden_content_keys(payload: Any, _depth: int = 0) -> list[str]:
    """Every key path in ``payload`` whose name marks it as hidden reasoning or secret material."""
    if _depth > _MAX_CONTENT_DEPTH:
        return ["<content nested beyond the permitted depth>"]
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            name = str(key).lower()
            if name not in ALLOWED_CONTENT_KEY_EXCEPTIONS and any(
                marker in name for marker in FORBIDDEN_CONTENT_KEY_MARKERS
            ):
                found.append(str(key))
            found.extend(forbidden_content_keys(value, _depth + 1))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            found.extend(forbidden_content_keys(item, _depth + 1))
    return found


def assert_content_is_safe(payload: Any, field: str = "content") -> None:
    """Raise when ``payload`` carries hidden reasoning or secret material. No redaction.

    Deliberately a rejection rather than a scrub: silently stripping a key would let a caller
    believe it stored something it did not, and would make the prohibition invisible in review.
    """
    leaks = forbidden_content_keys(payload)
    if leaks:
        raise ValueError(
            f"{field} may not carry hidden reasoning or secret material; "
            f"forbidden key(s): {sorted(set(leaks))}"
        )


class ActorPrincipal(BaseModel):
    """Who or what did this. A LOGICAL principal -- never an authenticated production identity."""

    principal_id: UUID
    principal_type: PrincipalType
    display_name: str = Field(min_length=1, max_length=200)
    status: PrincipalStatus = "active"
    created_at: datetime | None = None


class AgentProfile(BaseModel):
    """What a runtime agent is FOR, and what it declares it can do.

    ``capabilities`` is what the router matches against. Declaring a capability is not permission
    to exercise it: the tool policy profile and the L5 policy boundary still apply.
    ``transport_stream`` says HOW to reach this agent, never WHICH agent comes next.
    """

    agent_id: UUID
    principal_id: UUID
    agent_key: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    capabilities: tuple[str, ...] = ()
    transport_stream: str | None = None
    # References resolved at runtime by the existing secret-reference machinery. The profile
    # stores the NAME, never the material.
    tool_policy_profile: str | None = None
    model_provider_ref: str | None = None
    status: ProfileStatus = "active"


class ProjectTeamMembership(BaseModel):
    """Who is on this team -- a different question from who did this work.

    Membership is availability, not an execution record. Execution stays on Work Item -> Run
    (AT-D01 / INV-02).
    """

    membership_id: UUID
    project_id: UUID
    agent_principal_id: UUID
    functional_role: str = Field(min_length=1, max_length=100)
    membership_state: MembershipState = "active"
    joined_at: datetime | None = None
    left_at: datetime | None = None


class ConversationThread(BaseModel):
    thread_id: UUID
    project_id: UUID
    goal_ref: str = Field(min_length=1, max_length=500)
    work_item_id: UUID | None = None
    run_id: str | None = None
    thread_type: ThreadType
    state: ThreadState = "open"
    superseded_by: UUID | None = None
    created_at: datetime | None = None


class TeamMessageCreate(BaseModel):
    """An addressed, threaded message. At least one recipient channel must be set.

    A message with no recipient at all is the ambiguity that makes today's streams
    uncollaborative, so a broadcast must say so by setting ``recipient_team``.
    """

    thread_id: UUID
    project_id: UUID
    sender_principal_id: UUID
    message_type: MessageType
    summary: str = Field(min_length=1, max_length=2000)
    recipient_principal_id: UUID | None = None
    recipient_role: str | None = Field(default=None, max_length=100)
    recipient_team: bool = False
    parent_message_id: UUID | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: dict[str, Any] = Field(default_factory=dict)
    audit_ref: str | None = None

    @model_validator(mode="after")
    def _must_be_addressed(self) -> "TeamMessageCreate":
        if not (self.recipient_principal_id or self.recipient_role or self.recipient_team):
            raise ValueError(
                "a team message must name a recipient principal, a recipient role, or declare "
                "itself a team broadcast"
            )
        assert_content_is_safe(self.content, "content")
        assert_content_is_safe(self.artifact_refs, "artifact_refs")
        return self


class TeamMessage(TeamMessageCreate):
    message_id: UUID
    correlation_id: UUID | None = None
    created_at: datetime | None = None


class TeamDecision(BaseModel):
    """A coordination choice made BY the team.

    INV-03: this is not an Approval and not a ProductOwnerDecision. ``selected_option`` is
    free-form and must never be a Review Gate Action -- a team that could emit one would be
    accepting its own delivery.
    """

    decision_id: UUID
    project_id: UUID
    thread_id: UUID
    proposed_by: UUID
    options_considered: tuple[dict[str, Any], ...] = ()
    selected_option: str = Field(min_length=1, max_length=500)
    rationale_summary: str = Field(min_length=1, max_length=2000)
    dissent_summary: str | None = Field(default=None, max_length=2000)
    resulting_plan_revision_id: str | None = None
    audit_ref: str | None = None
    created_at: datetime | None = None


class Handoff(BaseModel):
    """Work transfer. Ownership moves on ``accepted``, never on ``offered``."""

    handoff_id: UUID
    project_id: UUID
    work_item_id: UUID | None = None
    from_principal_id: UUID
    to_principal_id: UUID
    reason: str = Field(min_length=1, max_length=1000)
    context_refs: dict[str, Any] = Field(default_factory=dict)
    state: HandoffState = "offered"
    audit_ref: str | None = None
    created_at: datetime | None = None
    accepted_at: datetime | None = None


__all__ = [
    "ALLOWED_CONTENT_KEY_EXCEPTIONS",
    "FORBIDDEN_CONTENT_KEY_MARKERS",
    "ActorPrincipal",
    "AgentProfile",
    "assert_content_is_safe",
    "forbidden_content_keys",
    "ConversationThread",
    "Handoff",
    "HandoffState",
    "HUMAN_ONLY_MESSAGE_TYPES",
    "MembershipState",
    "MessageType",
    "PrincipalType",
    "ProjectTeamMembership",
    "RoutingOutcome",
    "SYSTEM_ONLY_MESSAGE_TYPES",
    "TeamDecision",
    "TeamMessage",
    "TeamMessageCreate",
    "ThreadType",
]
