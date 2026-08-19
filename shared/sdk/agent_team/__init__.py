"""Step AT-M2-TEAM-CORE -- runtime team identity, addressed collaboration and capability routing.

Implements the AT-M1 L2 contract as runtime: principals exist, teams exist, agents address each
other durably, and the successor of a piece of work is decided at runtime from declared
capabilities instead of by a compile-time stream constant.
"""

from shared.sdk.agent_team.capabilities import (
    AGENT_CAPABILITY_SEED,
    APPROVAL_REQUIRED_CAPABILITIES,
    KNOWN_CAPABILITIES,
    AgentCapabilityDeclaration,
    declaration_for,
    requires_human_approval,
    seed_for,
)
from shared.sdk.agent_team.events import (
    STREAM_TEAM,
    STREAM_TEAM_BLOCKED,
    TEAM_EVENTS,
)
from shared.sdk.agent_team.models import (
    ActorPrincipal,
    AgentProfile,
    ConversationThread,
    Handoff,
    ProjectTeamMembership,
    TeamDecision,
    TeamMessage,
    TeamMessageCreate,
)
from shared.sdk.agent_team.router import (
    RoutingCandidate,
    RoutingDecision,
    RoutingRequest,
    route,
)
from shared.sdk.agent_team.service import TeamService
from shared.sdk.agent_team.store import TeamStore

__all__ = [
    "AGENT_CAPABILITY_SEED",
    "APPROVAL_REQUIRED_CAPABILITIES",
    "ActorPrincipal",
    "AgentCapabilityDeclaration",
    "AgentProfile",
    "ConversationThread",
    "Handoff",
    "KNOWN_CAPABILITIES",
    "ProjectTeamMembership",
    "RoutingCandidate",
    "RoutingDecision",
    "RoutingRequest",
    "STREAM_TEAM",
    "STREAM_TEAM_BLOCKED",
    "TEAM_EVENTS",
    "TeamDecision",
    "TeamMessage",
    "TeamMessageCreate",
    "TeamService",
    "TeamStore",
    "declaration_for",
    "requires_human_approval",
    "route",
    "seed_for",
]
