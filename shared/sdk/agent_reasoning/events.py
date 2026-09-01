"""Step AT-M3.1 -- audit vocabulary for reasoning invocations.

No new stream is introduced. AT-M3.1 does not publish to the team event stream (there is no
discussion loop yet to tell); it only records an audit event per invocation, the same way
``TeamService`` records one per routing decision.

AT-M3.4 (rebaselined) added three types alongside the original one, because one type could no
longer tell the truth once an invocation could be attempted more than once. The distinctions all
matter to somebody counting:

``reasoning_attempt_started``    one per ATTEMPT, carrying its attempt number. A takeover shows up
                                 here as attempt 2, so "how many times was a provider actually
                                 asked" is answerable from the audit trail rather than inferred.
``reasoning_attempt_superseded`` an attempt whose lease expired and whose result was discarded in
                                 favour of the attempt that took over. Recorded because a
                                 discarded provider call still happened and still cost something.
``reasoning_invoked``            the TERMINAL outcome, emitted once per invocation by the attempt
                                 that actually terminalized it. Unchanged in meaning.
``reasoning_replayed``           a caller that received an already-terminal outcome. Deliberately
                                 NOT ``reasoning_invoked``: a replay invoked nothing, and counting
                                 it as a success would inflate the number of reasoning calls the
                                 system believes it made.
"""

from __future__ import annotations

AUDIT_REASONING_INVOKED = "reasoning_invoked"
AUDIT_REASONING_ATTEMPT_STARTED = "reasoning_attempt_started"
AUDIT_REASONING_ATTEMPT_SUPERSEDED = "reasoning_attempt_superseded"
AUDIT_REASONING_REPLAYED = "reasoning_replayed"

__all__ = [
    "AUDIT_REASONING_ATTEMPT_STARTED",
    "AUDIT_REASONING_ATTEMPT_SUPERSEDED",
    "AUDIT_REASONING_INVOKED",
    "AUDIT_REASONING_REPLAYED",
]
