"""Step 61 -- controlled cleanup review builder.

A cleanup review is a REVIEW, never an execution. Only allowlisted classifications under
allowlisted runtime roots are eligible; arbitrary paths are rejected. database_dump /
redis_snapshot / audit_export / security_summary / release_evidence / cluster_runtime_state
are always blocked; kind / ArgoCD / active DB / active Redis scopes are always blocked.
Temporary traces and old build cache may be allowed; everything else requires approval.
The review NEVER deletes anything (cleanup_executed is always false).
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .models import CleanupReview

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "dr" / "controlled-cleanup-review-model.yaml"


class CleanupReviewError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@lru_cache(maxsize=1)
def _model() -> dict[str, Any]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("controlledCleanupReview", {}) or {}


def allowed_roots() -> list[str]:
    return list(_model().get("allowedCleanupRoots", []) or [])


def allowed_classifications() -> list[str]:
    return list(_model().get("allowedCleanupClassifications", []) or [])


def requires_approval_classifications() -> list[str]:
    return list(_model().get("requiresApprovalClassifications", []) or [])


def blocked_classifications() -> list[str]:
    return list(_model().get("blockedCleanupClassifications", []) or [])


def forbidden_scopes() -> list[str]:
    return list(_model().get("forbiddenCleanupScopes", []) or [])


def is_path_allowlisted(path: str) -> bool:
    """Reject arbitrary / traversal / absolute paths; only allowlisted runtime roots."""
    p = (path or "").strip().replace("\\", "/")
    if not p or p.startswith("/") or ".." in p.split("/"):
        return False
    return any(p.startswith(root) for root in allowed_roots())


def classify_candidate(path: str, classification: str) -> dict[str, Any]:
    """Decide allowed / blocked / requires_approval for one candidate. Pure, no deletion."""
    decision = "blocked"
    blocked_reason: str | None = None
    requires_approval = False

    if not is_path_allowlisted(path):
        blocked_reason = "arbitrary_or_non_allowlisted_path"
    elif classification in blocked_classifications():
        blocked_reason = f"classification_blocked:{classification}"
    elif classification in allowed_classifications():
        decision = "allowed"
    elif classification in requires_approval_classifications():
        decision = "requires_approval"
        requires_approval = True
        blocked_reason = "requires_operator_approval"
    else:
        blocked_reason = f"unknown_or_unlisted_classification:{classification}"

    return {
        "path": path,
        "classification": classification,
        "decision": decision,
        "requires_operator_approval": requires_approval,
        "requires_backup_before_cleanup": classification not in allowed_classifications(),
        "blocked_reason": blocked_reason,
    }


def build_cleanup_review(
    *,
    scope: str,
    candidates: list[dict[str, Any]] | None = None,
) -> CleanupReview:
    """Build a cleanup review from raw candidates [{path, classification, size_bytes}].

    A forbidden scope (kind / ArgoCD / active DB / Redis) blocks the whole review.
    """
    if scope in forbidden_scopes():
        raise CleanupReviewError(f"forbidden_cleanup_scope:{scope}")

    rows: list[dict[str, Any]] = []
    allowed = blocked = approval = 0
    size = 0
    for c in candidates or []:
        path = str(c.get("path", ""))
        classification = str(c.get("classification", ""))
        size += int(c.get("size_bytes", 0) or 0)
        row = classify_candidate(path, classification)
        if row["decision"] == "allowed":
            allowed += 1
        elif row["decision"] == "requires_approval":
            approval += 1
        else:
            blocked += 1
        rows.append(row)

    risk = "low"
    if blocked:
        risk = "high"
    elif approval:
        risk = "medium"

    return CleanupReview(
        cleanup_review_id=uuid.uuid4().hex,
        scope=scope,
        candidates=rows,
        allowed_count=allowed,
        blocked_count=blocked,
        requires_approval_count=approval,
        estimated_size_bytes=size,
        risk_level=risk,
        cleanup_executed=False,
    )
