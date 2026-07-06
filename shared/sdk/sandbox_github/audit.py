"""Step 59 -- sandbox draft PR audit event builder.

Builds redacted audit metadata for each sandbox draft-PR operation. Metadata always
carries actor / role / reason / linkage and production_executed=false; it never
carries a token, secret, raw prompt, or chain-of-thought.
"""

from __future__ import annotations

from typing import Any

from .redaction import redact

EVENTS = (
    "sandbox_github_draft_pr_requested",
    "sandbox_github_draft_pr_policy_checked",
    "sandbox_github_draft_branch_created",
    "sandbox_github_draft_evidence_committed",
    "sandbox_github_draft_pr_created",
    "sandbox_github_draft_pr_blocked",
    "sandbox_github_draft_pr_failed",
)


def build_audit_metadata(
    *,
    event_type: str,
    actor: str,
    role: str,
    reason: str,
    project_id: str | None,
    work_item_id: str | None,
    repository_key: str,
    mode: str,
    correlation_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event_type not in EVENTS:
        raise ValueError(f"unknown sandbox draft PR audit event: {event_type}")
    meta: dict[str, Any] = {
        "event_type": event_type,
        "actor": actor,
        "role": role,
        "reason": reason,
        "project_id": project_id,
        "work_item_id": work_item_id,
        "repository_key": repository_key,
        "mode": mode,
        "correlation_id": correlation_id,
        "production_executed": False,
    }
    if extra:
        meta.update(extra)
    return redact(meta)
