"""Step 59 (Stage 61A) -- sandbox GitHub draft PR flow SDK.

Sandbox-only: builds + (optionally, when explicitly enabled with a credential) creates
*draft* pull requests inside an allowlisted sandbox repository. No merge, no
ready-for-review, no workflow dispatch, no non-sandbox write, no production action.
"""

from __future__ import annotations

from .audit import EVENTS, build_audit_metadata
from .client import SandboxGitHubClient
from .dry_run import PlanError, build_plan
from .models import (
    ALLOWED_MODES,
    MODE_DRY_RUN,
    MODE_LIVE_SANDBOX,
    DraftPrPlan,
    DraftPrResult,
    SandboxRepo,
)
from .safety import sandbox_github_safety_fields
from .store import SandboxDraftPrStore

__all__ = [
    "ALLOWED_MODES",
    "MODE_DRY_RUN",
    "MODE_LIVE_SANDBOX",
    "DraftPrPlan",
    "DraftPrResult",
    "SandboxRepo",
    "SandboxGitHubClient",
    "SandboxDraftPrStore",
    "PlanError",
    "build_plan",
    "build_audit_metadata",
    "sandbox_github_safety_fields",
    "EVENTS",
]
