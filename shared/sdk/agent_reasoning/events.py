"""Step AT-M3.1 -- audit vocabulary for reasoning invocations.

No new stream is introduced. AT-M3.1 does not publish to the team event stream (there is no
discussion loop yet to tell); it only records an audit event per invocation, the same way
``TeamService`` records one per routing decision.
"""

from __future__ import annotations

AUDIT_REASONING_INVOKED = "reasoning_invoked"

__all__ = ["AUDIT_REASONING_INVOKED"]
