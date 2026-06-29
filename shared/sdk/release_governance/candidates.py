"""Step 60 -- release candidate builder.

Builds a release candidate from delivery / work-item / sandbox-draft-PR linkage. The
target environment is validated against the policy (never production); production_ready
is always false.
"""

from __future__ import annotations

import uuid

from . import policy
from .models import ReleaseCandidate


class CandidateError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_candidate(
    *,
    project_id: str | None,
    version_label: str,
    target_environment: str | None = None,
    work_item_ids: list[str] | None = None,
    delivery_package_ids: list[str] | None = None,
    sandbox_draft_pr_ids: list[str] | None = None,
) -> ReleaseCandidate:
    env, blocked = policy.validate_environment(target_environment)
    if blocked:
        raise CandidateError(blocked)
    return ReleaseCandidate(
        release_candidate_id=uuid.uuid4().hex,
        project_id=project_id,
        work_item_ids=list(work_item_ids or []),
        delivery_package_ids=list(delivery_package_ids or []),
        sandbox_draft_pr_ids=list(sandbox_draft_pr_ids or []),
        version_label=version_label,
        target_environment=env,
        status="draft",
        production_ready=False,
    )
