"""Step AT-M3.6B.1 -- what is allowed to leave the local boundary for a live reasoning call.

The Product Owner authorized sending "locally-authored non-production control-plane reasoning
content" to Anthropic. This module is the mechanical statement of that sentence: a per-verb
allowlist of the exact context fields AT-M3.3 and AT-M3.4 actually build, applied before any wire
call and before any spend.

WHY AN ALLOWLIST RATHER THAN SERIALIZING ``ReasoningRequest.context``. ``context`` is a free-form
``dict[str, Any]``. Serializing it wholesale would mean the set of things that leave the boundary is
whatever some caller happened to put in a dict -- and that set would change silently whenever any
upstream service added a field. Every field below traces to a line in
``agent_deliberation/models.py::build_turn_context`` or
``agent_planning_decision/service.py::_author_plan``; a key that is not on the list does not get
quietly dropped, it fails the call, because a silent drop would let an upstream change that SHOULD
have been reviewed pass as a working call with a missing field.

The allowlist is on TOP-LEVEL keys. Nested values are not re-enumerated because they are already
bounded by their own closed schemas (``PlanContent``, and the clipped message summaries M3.3 builds)
and because the whole projection goes back through ``assert_content_is_safe`` -- the same screen a
TeamMessage passes -- before it is measured.

Non-production only. AT-M3.6B.1 makes ZERO external calls; this module bounds a payload that, in
this slice, is only ever handed to an in-process fake transport.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from shared.sdk.agent_team.models import assert_content_is_safe

#: The maximum serialized size of one outbound reasoning context, in bytes (32 KiB).
#:
#: Enforced by this application, never delegated to the provider's context-window error: a provider
#: that rejects an oversized request has already been paid for the attempt in latency and may have
#: been paid in tokens, and a bound that only exists on the other side of the boundary is not a
#: bound on what left the boundary.
MAX_CONTEXT_BYTES = 32 * 1024

# The fields AT-M3.3 assembles for a discussion turn. Every one is a clipped, durable, approved
# artifact: the Goal's own statement and criteria, the speaker's declared role and capabilities, the
# last few TeamMessage SUMMARIES (never bodies), and the current plan's objective and step titles.
_DELIBERATION_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "topic",
        "round",
        "goal_statement",
        "goal_acceptance_criteria",
        "goal_constraints",
        "speaker_role",
        "speaker_capabilities",
        "recent_messages",
        "plan_revision_number",
        "plan_objective",
        "plan_step_titles",
        "proposal_summary",
    }
)

# What AT-M3.4's planner is shown: the Goal it serves, what the room concluded, a capped sample of
# what was proposed and objected to, and the plan the Goal currently has.
_PLANNER_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "goal_statement",
        "acceptance_criteria",
        "goal_constraints",
        "selected_option",
        "options_considered",
        "dissent_summary",
        "proposal_summaries",
        "challenge_summaries",
        "current_plan",
    }
)

ALLOWED_CONTEXT_KEYS: dict[str, frozenset[str]] = {
    "propose": _DELIBERATION_CONTEXT_KEYS,
    "critique": _DELIBERATION_CONTEXT_KEYS,
    # The convergence turn additionally names the options the room put on the table.
    "summarize_decision": _DELIBERATION_CONTEXT_KEYS | frozenset({"options_considered"}),
    "decompose_plan": _PLANNER_CONTEXT_KEYS,
}


class EgressViolationError(ValueError):
    """A reasoning context carries something that is not authorized to leave the boundary."""


def project_context(verb: str, context: Mapping[str, Any]) -> dict[str, Any]:
    """The approved outbound projection of ``context`` for ``verb``.

    Fails closed on an unrecognised verb and on any key outside that verb's allowlist. The error
    names the offending KEYS and never their values -- an unapproved field is exactly the field
    whose content must not be copied into an exception that will be logged.
    """
    allowed = ALLOWED_CONTEXT_KEYS.get(verb)
    if allowed is None:
        raise EgressViolationError(f"reasoning verb {verb!r} has no approved outbound egress shape")
    unapproved = sorted(str(key) for key in context if str(key) not in allowed)
    if unapproved:
        raise EgressViolationError(
            f"context for verb {verb!r} carries field(s) not authorized to leave the local "
            f"boundary: {unapproved}"
        )
    projection = {str(key): context[key] for key in sorted(context, key=str)}
    # Defense in depth, and not redundant: the ReasoningRequest validator screened the context the
    # CALLER built, while this screens the payload that is actually about to leave. They are the
    # same check on two different objects, and only the second one is the boundary.
    assert_content_is_safe(projection, field=f"egress:{verb}")
    return projection


def serialize_context(projection: Mapping[str, Any]) -> bytes:
    """The exact bytes an outbound context is measured in. Deterministic."""
    return json.dumps(
        projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def context_size(projection: Mapping[str, Any]) -> int:
    return len(serialize_context(projection))


def assert_context_within_size(
    projection: Mapping[str, Any], *, limit: int = MAX_CONTEXT_BYTES
) -> int:
    """Raise when the approved projection is larger than the outbound bound. Returns its size."""
    size = context_size(projection)
    if size > limit:
        raise EgressViolationError(
            f"outbound reasoning context is {size} bytes, which exceeds the authorized maximum of "
            f"{limit} bytes"
        )
    return size


def approved_outbound_context(verb: str, context: Mapping[str, Any]) -> dict[str, Any]:
    """Project and bound in one call. The only function the adapter uses."""
    projection = project_context(verb, context)
    assert_context_within_size(projection)
    return projection


__all__ = [
    "ALLOWED_CONTEXT_KEYS",
    "MAX_CONTEXT_BYTES",
    "EgressViolationError",
    "approved_outbound_context",
    "assert_context_within_size",
    "context_size",
    "project_context",
    "serialize_context",
]
