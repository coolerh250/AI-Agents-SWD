"""Step AT-M2-TEAM-CORE -- the capability-based runtime router.

This is the module that takes routing authority away from compile-time stream constants. Given a
requested capability and the CURRENT team, it decides which principal receives the work and says
why. Change the team -- remove a member, disable a capability -- and the same request routes
somewhere else, or honestly reports that nobody is eligible.

Deliberately pure: it performs no I/O, so a routing decision is a function of the team as it was
read, and the same inputs always produce the same decision and the same reason. Persistence and
audit are the caller's job (``service.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.sdk.agent_team.capabilities import requires_human_approval

# Workflow states in which no work may be routed at all. A workflow parked on a human decision
# must not have its next step chosen for it.
NON_ROUTABLE_WORKFLOW_STAGES = frozenset({"waiting_approval", "halted", "blocked_pending_approval"})


@dataclass(frozen=True)
class RoutingCandidate:
    """One team member considered for a routing request."""

    principal_id: str
    agent_key: str
    role: str
    capabilities: frozenset[str]
    transport_stream: str | None = None
    membership_state: str = "active"
    profile_status: str = "active"

    def ineligibility(self, capability: str) -> str:
        """Why this candidate cannot take ``capability``; empty when it can."""
        if self.membership_state != "active":
            return f"membership_state={self.membership_state}"
        if self.profile_status != "active":
            return f"profile_status={self.profile_status}"
        if capability not in self.capabilities:
            return "capability_not_declared"
        if not self.transport_stream:
            return "no_transport_stream"
        return ""


@dataclass(frozen=True)
class RoutingRequest:
    requested_capability: str
    project_id: str
    workflow_stage: str = ""
    work_item_id: str | None = None
    task_id: str | None = None
    workflow_id: str | None = None
    # An optional preference, never a guarantee. A role hint that matches nobody eligible is
    # ignored rather than allowed to override capability.
    preferred_role: str | None = None


@dataclass(frozen=True)
class RoutingDecision:
    outcome: str  # selected | no_eligible_agent | requires_human_approval
    requested_capability: str
    reason: str
    selected_principal_id: str | None = None
    selected_role: str | None = None
    selected_agent_key: str | None = None
    selected_stream: str | None = None
    candidates_considered: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def selected(self) -> bool:
        return self.outcome == "selected"

    def as_record(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "requested_capability": self.requested_capability,
            "reason": self.reason,
            "selected_principal_id": self.selected_principal_id,
            "selected_role": self.selected_role,
            "selected_agent_key": self.selected_agent_key,
            "selected_stream": self.selected_stream,
            "candidates_considered": list(self.candidates_considered),
        }


def _considered(candidate: RoutingCandidate, capability: str) -> dict[str, Any]:
    reason = candidate.ineligibility(capability)
    return {
        "principal_id": candidate.principal_id,
        "agent_key": candidate.agent_key,
        "role": candidate.role,
        "eligible": not reason,
        "rejected_because": reason or None,
    }


def _rank(candidate: RoutingCandidate, request: RoutingRequest) -> tuple:
    """Deterministic preference order among eligible candidates.

    1. A candidate matching ``preferred_role`` wins, when one is eligible.
    2. Otherwise the most SPECIALISED candidate wins -- the one declaring the fewest capabilities
       -- so a generalist does not absorb work a dedicated agent exists for.
    3. ``agent_key`` breaks the remaining ties, so the decision is reproducible.
    """
    role_miss = 0 if request.preferred_role and candidate.role == request.preferred_role else 1
    return (role_miss, len(candidate.capabilities), candidate.agent_key)


def route(request: RoutingRequest, candidates: list[RoutingCandidate]) -> RoutingDecision:
    """Choose who takes ``request.requested_capability`` on this team, and say why."""
    capability = request.requested_capability
    considered = tuple(_considered(c, capability) for c in candidates)

    if not capability:
        return RoutingDecision(
            outcome="no_eligible_agent",
            requested_capability=capability,
            reason="no capability was requested, so no agent can be selected",
            candidates_considered=considered,
        )

    # The policy boundary comes first: a production-effect capability is never routed to an agent,
    # however capable the team is. Routing selects a worker; approving is a human act (L5).
    if requires_human_approval(capability):
        return RoutingDecision(
            outcome="requires_human_approval",
            requested_capability=capability,
            reason=(
                f"{capability!r} has production effect; it is referred to the human approval "
                "boundary rather than routed to an agent"
            ),
            candidates_considered=considered,
        )

    if request.workflow_stage in NON_ROUTABLE_WORKFLOW_STAGES:
        return RoutingDecision(
            outcome="no_eligible_agent",
            requested_capability=capability,
            reason=(
                f"the workflow is at stage {request.workflow_stage!r}, which is waiting on a "
                "human decision; nothing is routed until it clears"
            ),
            candidates_considered=considered,
        )

    eligible = [c for c in candidates if not c.ineligibility(capability)]
    if not eligible:
        return RoutingDecision(
            outcome="no_eligible_agent",
            requested_capability=capability,
            reason=(
                f"no active team member declares {capability!r} "
                f"({len(candidates)} member(s) considered)"
            ),
            candidates_considered=considered,
        )

    winner = min(eligible, key=lambda c: _rank(c, request))
    if request.preferred_role and winner.role == request.preferred_role:
        why = f"declares {capability!r} and matches the preferred role {request.preferred_role!r}"
    elif len(eligible) == 1:
        why = f"the only active team member declaring {capability!r}"
    else:
        why = (
            f"declares {capability!r} and is the most specialised of {len(eligible)} eligible "
            f"members ({len(winner.capabilities)} declared capability/capabilities)"
        )
    return RoutingDecision(
        outcome="selected",
        requested_capability=capability,
        reason=f"{winner.agent_key} {why}",
        selected_principal_id=winner.principal_id,
        selected_role=winner.role,
        selected_agent_key=winner.agent_key,
        selected_stream=winner.transport_stream,
        candidates_considered=considered,
    )


__all__ = [
    "NON_ROUTABLE_WORKFLOW_STAGES",
    "RoutingCandidate",
    "RoutingDecision",
    "RoutingRequest",
    "route",
]
