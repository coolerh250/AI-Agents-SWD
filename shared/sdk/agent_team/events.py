"""Step AT-M2-TEAM-CORE -- team collaboration stream and event vocabulary.

One new stream. The existing per-agent streams keep their meaning as work transport; this stream
carries what the TEAM did -- who joined, who addressed whom, and how a successor was chosen.
"""

from __future__ import annotations

STREAM_TEAM = "stream.team"

# Published when work cannot be routed because no eligible team member exists. Publishing here is
# the honest terminal state: the alternative -- quietly falling back to a compile-time successor
# -- is exactly the behaviour AT-M2 removes.
STREAM_TEAM_BLOCKED = "stream.team.blocked"

EVENT_TEAM_FORMED = "team.formed"
EVENT_MEMBER_JOINED = "team.member_joined"
EVENT_MEMBER_CHANGED = "team.member_changed"
EVENT_MESSAGE_POSTED = "team.message_posted"
EVENT_ROUTING_DECIDED = "team.routing_decided"
EVENT_ROUTING_BLOCKED = "team.routing_blocked"
EVENT_HANDOFF_OFFERED = "team.handoff_offered"
EVENT_HANDOFF_ACCEPTED = "team.handoff_accepted"
EVENT_DECISION_RECORDED = "team.decision_recorded"

TEAM_EVENTS = frozenset(
    {
        EVENT_TEAM_FORMED,
        EVENT_MEMBER_JOINED,
        EVENT_MEMBER_CHANGED,
        EVENT_MESSAGE_POSTED,
        EVENT_ROUTING_DECIDED,
        EVENT_ROUTING_BLOCKED,
        EVENT_HANDOFF_OFFERED,
        EVENT_HANDOFF_ACCEPTED,
        EVENT_DECISION_RECORDED,
    }
)

# Audit decision_type values, one per consequential team act.
AUDIT_TEAM_FORMED = "team_formed"
AUDIT_MEMBER_JOINED = "team_member_joined"
AUDIT_MEMBER_CHANGED = "team_member_changed"
AUDIT_MESSAGE_POSTED = "team_message_posted"
AUDIT_ROUTING_DECIDED = "team_routing_decided"
AUDIT_HANDOFF = "team_handoff"
AUDIT_DECISION = "team_decision"

__all__ = [
    "AUDIT_DECISION",
    "AUDIT_HANDOFF",
    "AUDIT_MEMBER_CHANGED",
    "AUDIT_MEMBER_JOINED",
    "AUDIT_MESSAGE_POSTED",
    "AUDIT_ROUTING_DECIDED",
    "AUDIT_TEAM_FORMED",
    "EVENT_DECISION_RECORDED",
    "EVENT_HANDOFF_ACCEPTED",
    "EVENT_HANDOFF_OFFERED",
    "EVENT_MEMBER_CHANGED",
    "EVENT_MEMBER_JOINED",
    "EVENT_MESSAGE_POSTED",
    "EVENT_ROUTING_BLOCKED",
    "EVENT_ROUTING_DECIDED",
    "EVENT_TEAM_FORMED",
    "STREAM_TEAM",
    "STREAM_TEAM_BLOCKED",
    "TEAM_EVENTS",
]
