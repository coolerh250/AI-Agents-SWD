"""Step AT-M3.2 -- audit vocabulary for Goal and PlanRevision.

No new stream is introduced, matching AT-M3.1: this slice has no discussion loop to tell, so it
records audit events only, the way ``TeamService`` does for routing decisions.

An event identifies WHAT happened to WHICH revision, BY WHOM, and HOW IT ENDED. It never carries
the plan payload, the diff body, a rationale, or any reasoning about why the plan changed --
those live in the durable row, which is queryable, rather than being duplicated into an audit
summary where they would be much harder to redact later.
"""

from __future__ import annotations

AUDIT_GOAL_CREATED = "goal_created"
AUDIT_PLAN_REVISION_CREATED = "plan_revision_created"
AUDIT_PLAN_REVISION_SUPERSEDED = "plan_revision_superseded"
AUDIT_PLAN_REVISION_STALE_REJECTED = "plan_revision_stale_rejected"

__all__ = [
    "AUDIT_GOAL_CREATED",
    "AUDIT_PLAN_REVISION_CREATED",
    "AUDIT_PLAN_REVISION_STALE_REJECTED",
    "AUDIT_PLAN_REVISION_SUPERSEDED",
]
