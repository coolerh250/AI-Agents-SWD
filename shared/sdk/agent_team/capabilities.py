"""Step AT-M2-TEAM-CORE -- the runtime capability vocabulary and the agent seed registry.

A capability answers "what work can this agent take", which is the question the router asks. It
deliberately does NOT answer "who comes after whom": that answer is produced at runtime from
membership plus declared capabilities, and it changes when the team changes.

This module is a SEED, not the routing authority. It supplies the profiles a project team is
formed from; once formed, the team's own membership rows decide who is eligible. Editing a
declaration here changes who *can* be recruited, never who *is* next.
"""

from __future__ import annotations

from dataclasses import dataclass

# The canonical capability vocabulary. Kept small on purpose: every entry must correspond to work
# some runtime agent can actually take today.
ANALYZE_REQUIREMENTS = "analyze_requirements"
CLARIFY_REQUIREMENTS = "clarify_requirements"
GENERATE_CODE = "generate_code"
FIX_DEFECTS = "fix_defects"
VERIFY_QUALITY = "verify_quality"
PLAN_DEPLOYMENT = "plan_deployment"
PLAN_PROJECT = "plan_project"
REVIEW_DESIGN = "review_design"
PACKAGE_DELIVERY = "package_delivery"

KNOWN_CAPABILITIES = frozenset(
    {
        ANALYZE_REQUIREMENTS,
        CLARIFY_REQUIREMENTS,
        GENERATE_CODE,
        FIX_DEFECTS,
        VERIFY_QUALITY,
        PLAN_DEPLOYMENT,
        PLAN_PROJECT,
        REVIEW_DESIGN,
        PACKAGE_DELIVERY,
    }
)

# Capabilities whose exercise would have production effect. The router never selects an agent for
# one of these: it returns ``requires_human_approval`` so the existing L5 approval boundary
# decides. Routing selects a worker; it has never been able to authorize an action, and this list
# is what keeps that true as new capabilities are added.
APPROVAL_REQUIRED_CAPABILITIES = frozenset(
    {
        "execute_production_action",
        "deploy_production",
        "publish_external_artifact",
    }
)


@dataclass(frozen=True)
class AgentCapabilityDeclaration:
    """What one runtime agent declares about itself when it joins a team."""

    agent_key: str
    role: str
    capabilities: tuple[str, ...]
    # Transport only: how to reach this agent once the router has selected it.
    transport_stream: str
    tool_policy_profile: str | None = None
    model_provider_ref: str | None = None


# The runtime agents that exist and can be recruited onto a project team. backend-agent and
# frontend-agent are deliberately absent: their directories hold no runtime, so declaring them
# would let the router select an agent that cannot receive work.
#
# Every capability in KNOWN_CAPABILITIES must appear here (asserted by
# _assert_every_capability_has_an_owner below). A vocabulary entry nobody serves is worse than
# no entry at all: it advertises work the router can never place, and turns a missing runtime
# owner into an indistinguishable "no eligible agent" at dispatch time.
AGENT_CAPABILITY_SEED: tuple[AgentCapabilityDeclaration, ...] = (
    AgentCapabilityDeclaration(
        agent_key="requirement-agent",
        role="requirement",
        capabilities=(ANALYZE_REQUIREMENTS, CLARIFY_REQUIREMENTS),
        transport_stream="stream.requirements",
    ),
    AgentCapabilityDeclaration(
        agent_key="development-agent",
        role="development",
        capabilities=(GENERATE_CODE,),
        transport_stream="stream.development",
    ),
    AgentCapabilityDeclaration(
        agent_key="development-agent-autofix",
        role="development",
        capabilities=(FIX_DEFECTS,),
        transport_stream="stream.development.autofix",
    ),
    AgentCapabilityDeclaration(
        agent_key="qa-agent",
        role="qa",
        capabilities=(VERIFY_QUALITY,),
        transport_stream="stream.qa",
    ),
    AgentCapabilityDeclaration(
        agent_key="devops-agent",
        role="devops",
        capabilities=(PLAN_DEPLOYMENT,),
        transport_stream="stream.deployments",
    ),
    AgentCapabilityDeclaration(
        agent_key="project-planner-agent",
        role="planner",
        capabilities=(PLAN_PROJECT,),
        transport_stream="stream.project_planning",
    ),
    AgentCapabilityDeclaration(
        agent_key="design-review-agent",
        role="design_review",
        capabilities=(REVIEW_DESIGN,),
        transport_stream="stream.design_review",
    ),
    AgentCapabilityDeclaration(
        agent_key="delivery-package-agent",
        role="delivery",
        capabilities=(PACKAGE_DELIVERY,),
        transport_stream="stream.delivery_package",
    ),
)


def _assert_every_capability_has_an_owner() -> None:
    """A capability nobody can serve must not be advertised.

    Enforced at import so the vocabulary and the runtime cannot drift apart silently: adding a
    capability without an owner fails immediately rather than at the first routing request.
    """
    owned: set[str] = set()
    for declaration in AGENT_CAPABILITY_SEED:
        owned |= set(declaration.capabilities)
    unowned = KNOWN_CAPABILITIES - owned
    if unowned:
        raise RuntimeError(
            f"capabilities advertised with no runtime owner: {sorted(unowned)}. "
            "Declare an owning agent or remove them from KNOWN_CAPABILITIES."
        )
    unknown = owned - KNOWN_CAPABILITIES
    if unknown:
        raise RuntimeError(f"agents declare capabilities outside the vocabulary: {sorted(unknown)}")


_assert_every_capability_has_an_owner()


def seed_for(agent_keys: tuple[str, ...] | None = None) -> tuple[AgentCapabilityDeclaration, ...]:
    """The declarations for ``agent_keys``, or every declaration when none are named."""
    if agent_keys is None:
        return AGENT_CAPABILITY_SEED
    wanted = set(agent_keys)
    return tuple(d for d in AGENT_CAPABILITY_SEED if d.agent_key in wanted)


def declaration_for(agent_key: str) -> AgentCapabilityDeclaration | None:
    for declaration in AGENT_CAPABILITY_SEED:
        if declaration.agent_key == agent_key:
            return declaration
    return None


def requires_human_approval(capability: str) -> bool:
    return capability in APPROVAL_REQUIRED_CAPABILITIES


__all__ = [
    "AGENT_CAPABILITY_SEED",
    "ANALYZE_REQUIREMENTS",
    "APPROVAL_REQUIRED_CAPABILITIES",
    "AgentCapabilityDeclaration",
    "CLARIFY_REQUIREMENTS",
    "FIX_DEFECTS",
    "GENERATE_CODE",
    "KNOWN_CAPABILITIES",
    "PACKAGE_DELIVERY",
    "PLAN_DEPLOYMENT",
    "PLAN_PROJECT",
    "REVIEW_DESIGN",
    "VERIFY_QUALITY",
    "declaration_for",
    "requires_human_approval",
    "seed_for",
]
