"""Step AT-M3.3 -- audit vocabulary for bounded team discussion.

Following AT-M3.1 and AT-M3.2: no new stream is introduced, only audit decision types. An event
records WHICH discussion moved, WHO spoke, in WHICH round, and HOW it ended -- identifiers,
counters and dispositions. Never a message body, never plan prose, never a rationale, never
anything a provider returned. The message itself is already durable and queryable in
``team_messages``, where AT-M2's own redaction rules govern it; duplicating its text into an audit
summary would put the same content somewhere much harder to redact later.
"""

from __future__ import annotations

AUDIT_DISCUSSION_OPENED = "discussion_opened"
AUDIT_DISCUSSION_TURN_RECORDED = "discussion_turn_recorded"
AUDIT_DISCUSSION_TURN_LOST = "discussion_turn_lost"
AUDIT_DISCUSSION_CLOSED = "discussion_closed"

__all__ = [
    "AUDIT_DISCUSSION_CLOSED",
    "AUDIT_DISCUSSION_OPENED",
    "AUDIT_DISCUSSION_TURN_LOST",
    "AUDIT_DISCUSSION_TURN_RECORDED",
]
