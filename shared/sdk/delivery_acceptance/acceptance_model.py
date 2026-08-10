"""Step 66D-BE1 -- delivery acceptance domain model.

Pure definitions and predicates for the five canonical acceptance entities (migration 036). No
I/O, no HTTP, no event, no workflow. Every vocabulary here mirrors a canonical artifact and adds
nothing:

    66D-D01  six Review Gate Actions, three Product Owner Final Decisions, disjoint enums
    66D-D02  nine delivery review statuses; the decision record is the authority, the status a
             projection
    66D-D04  DeliverySubmission is the acceptance aggregate; legacy DeliveryPackage is untouched
    66D-D05  DeliveryReviewTask active state is STRUCTURAL -- closed_at IS NULL -- and there is no
             review-task lifecycle enum at all

The 66D-D05 predicates below are the only sanctioned way to ask whether a review task is active.
There is deliberately no OPEN/CLOSED value, no status string and no mapping from the submission
status: `review_task_is_active` reads `closed_at` and nothing else.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.tasks.rbac import TASK_ROLES

# ---- Canonical vocabularies ---------------------------------------------------------------------

# The nine canonical DeliverySubmission statuses (66D-D02). Exactly nine; a tenth product-visible
# status must never be added here without a new Product Owner decision.
SUBMISSION_STATUSES: frozenset[str] = frozenset(
    {
        "DRAFT",
        "SUBMITTED",
        "UNDER_REVIEW",
        "CHANGES_REQUESTED",
        "QA_RERUN_REQUESTED",
        "ACCEPTED",
        "REJECTED",
        "ARCHIVED",
        "EXPIRED",
    }
)

# The six Review Gate Actions (66D-D01). ACCEPTED_WITH_FOLLOW_UP is a decision, never an action
# (D01-R9).
REVIEW_ACTION_TYPES: frozenset[str] = frozenset(
    {"ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"}
)

# The three Product Owner Final Decisions (66D-D01). No Review Gate Action value belongs here
# (D01-R8).
PO_DECISION_TYPES: frozenset[str] = frozenset({"ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED"})

# AcceptanceFollowUpItem lifecycle, and ONLY AcceptanceFollowUpItem's. 66D-D05 (D05-R8) forbids
# reusing this set as a DeliveryReviewTask lifecycle.
FOLLOW_UP_STATUSES: frozenset[str] = frozenset({"OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED"})

# Actions that require a reason, and the action that requires a re-verification scope (ARCH1
# section 3). Mirrored by migration 036 chk_dra_reason_required / chk_dra_rerun_qa_scope.
REASON_REQUIRED_ACTIONS: frozenset[str] = frozenset(
    {"REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "REJECT"}
)
SCOPE_REQUIRED_ACTIONS: frozenset[str] = frozenset({"RERUN_QA"})

# Review Gate Actions that carry a Product Owner Final Decision. The other four carry none -- that
# separation is the substance of 66D-D01 and is NOT enforced by BE1 persistence; recording the two
# atomically is Step 66D-BE3 action policy.
DECISION_BEARING_ACTIONS: frozenset[str] = frozenset({"ACCEPT", "REJECT"})

# Assignment roles are the canonical TASK_ROLES. BE1 references this set; it never modifies RBAC.
ASSIGNABLE_ROLES: frozenset[str] = TASK_ROLES


# ---- 66D-D05 structural active state ------------------------------------------------------------
#
# active := closed_at IS NULL        closed := closed_at IS NOT NULL
#
# closed_at is a STRUCTURAL marker. It never implies ACCEPTED, REJECTED, EXPIRED, ARCHIVED, a
# recorded ProductOwnerDecision, completed QA or a terminal submission status (D05-R7). There is no
# DeliveryReviewTask lifecycle enum, so there is nothing else to read.

REVIEW_TASK_ACTIVE_PREDICATE_SQL = "closed_at IS NULL"
REVIEW_TASK_CLOSED_PREDICATE_SQL = "closed_at IS NOT NULL"


def review_task_is_active(row: dict[str, Any]) -> bool:
    """Whether a DeliveryReviewTask row is structurally ACTIVE (66D-D05, D05-R1).

    Reads `closed_at` and nothing else. It never consults a status column (there is none), never
    consults the submission's status (D05-R3), and returns no lifecycle value (D05-R8).
    """
    return row.get("closed_at") is None


def review_task_is_closed(row: dict[str, Any]) -> bool:
    """The exact complement of `review_task_is_active` (66D-D05)."""
    return row.get("closed_at") is not None


# ---- Validators -------------------------------------------------------------------------------


def assert_submission_status(status: str) -> str:
    if status not in SUBMISSION_STATUSES:
        raise ValueError(f"unknown delivery submission status: {status}")
    return status


def assert_review_action_type(action_type: str) -> str:
    if action_type not in REVIEW_ACTION_TYPES:
        raise ValueError(f"unknown review gate action: {action_type}")
    return action_type


def assert_po_decision_type(decision_type: str) -> str:
    if decision_type not in PO_DECISION_TYPES:
        raise ValueError(f"unknown product owner decision: {decision_type}")
    return decision_type


def assert_follow_up_status(status: str) -> str:
    if status not in FOLLOW_UP_STATUSES:
        raise ValueError(f"unknown acceptance follow-up status: {status}")
    return status


def assert_assigned_roles(roles: list[str]) -> list[str]:
    unknown = sorted(set(roles) - ASSIGNABLE_ROLES)
    if unknown:
        raise ValueError(f"roles are not canonical TASK_ROLES: {unknown}")
    return roles


# ---- Effective decision -------------------------------------------------------------------------


def effective_decision(decisions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The current effective ProductOwnerDecision for one submission (ARCH1 section 4).

    The row with the highest `decision_version` that is not itself superseded by another row in
    `decisions`. Superseded rows stay in the list -- history is never deleted or hidden (D02-R3);
    this only selects which one is currently in force.
    """
    if not decisions:
        return None
    superseded = {d["supersedes_decision_id"] for d in decisions if d.get("supersedes_decision_id")}
    live = [d for d in decisions if d["decision_id"] not in superseded]
    if not live:
        return None
    return max(live, key=lambda d: int(d["decision_version"]))


def projected_submission_status(decision: dict[str, Any] | None) -> str | None:
    """The delivery review status ACCEPTED/REJECTED projected from an effective decision (D02-R4,
    D02-R5). Returns None when no decision is in force -- absence of a decision is NOT acceptance.

    This is a pure projection helper. BE1 does not write it anywhere: applying it to a submission
    row is Step 66D-BE3 transaction policy.
    """
    if decision is None:
        return None
    decision_type = assert_po_decision_type(decision["decision_type"])
    if decision_type == "REJECTED":
        return "REJECTED"
    return "ACCEPTED"
