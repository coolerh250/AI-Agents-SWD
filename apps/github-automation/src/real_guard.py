"""Stage 23 controlled-real GitHub safety guard.

Real GitHub writes (issue / branch / file / PR / checks) are allowed only
through ``POST /github/workflow/real-test-pr`` and only when EVERY
condition below holds:

* ``GITHUB_TOKEN`` env var is set.
* ``RUN_REAL_GITHUB_TEST=true`` env var is set.
* ``GITHUB_TEST_REPO`` env var is set.
* The request's ``repo`` equals ``GITHUB_TEST_REPO``.
* ``branch_name`` starts with ``ai-agents-test/``.
* ``title`` starts with ``[AI-Agents-SWD Test]``.
* ``base_branch`` is **not** a production-shaped branch
  (``production`` / ``prod`` / ``release`` / ``release/*``).
* ``dry_run`` is exactly ``False`` (not ``None``, not omitted).
* ``file_path`` lives under ``docs/github-real-test/``.
* ``file_content`` carries the required markers:
  ``task_id`` / ``workflow_id`` / ``generated_by=github-automation`` /
  ``real_github_test=true`` / ``production_executed=false``.
* PR ``body`` carries the six required sections, including the
  Stage 23 mandatory ``## Safety Notes`` section.

Any failure returns a structured ``GuardResult`` with ``allowed=False``
and an explicit ``reason``. Callers turn that into HTTP 409 + an audit
event + a ``github_real_test_blocked_total`` increment. The guard never
references the token value, never returns it, never logs it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

ALLOWED_BRANCH_PREFIX = "ai-agents-test/"
ALLOWED_TITLE_PREFIX = "[AI-Agents-SWD Test]"
ALLOWED_FILE_PREFIX = "docs/github-real-test/"
FORBIDDEN_BASE_BRANCHES = {"production", "prod"}
FORBIDDEN_BASE_PREFIXES = ("release/",)

REQUIRED_PR_SECTIONS = (
    "## Summary",
    "## Changed Files",
    "## Risk Assessment",
    "## Test Result",
    "## Rollback Plan",
    "## Safety Notes",
)

REQUIRED_FILE_MARKERS = (
    "task_id",
    "workflow_id",
    "generated_by=github-automation",
    "real_github_test=true",
    "production_executed=false",
)


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    repo: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        """Public response shape — never includes any token-shaped field."""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "repo": self.repo,
            "details": self.details,
        }


def _env(name: str, env: dict[str, str] | None) -> str:
    src = env if env is not None else os.environ
    return (src.get(name, "") or "").strip()


def _bool_env(name: str, env: dict[str, str] | None) -> bool:
    return _env(name, env).lower() == "true"


def _base_branch_is_forbidden(base_branch: str) -> bool:
    branch = (base_branch or "").strip().lower()
    if not branch:
        return False
    if branch in FORBIDDEN_BASE_BRANCHES:
        return True
    return any(branch.startswith(p) for p in FORBIDDEN_BASE_PREFIXES)


def evaluate_real_test_request(
    *,
    repo: str,
    base_branch: str,
    branch_name: str,
    title: str,
    body: str,
    file_path: str,
    file_content: str,
    dry_run: Any,
    env: dict[str, str] | None = None,
) -> GuardResult:
    """Validate every Stage 23 pre-condition. Stops at the first violation.

    ``dry_run`` is checked with ``is False`` so an omitted/``None`` value
    cannot accidentally enable a real write — the caller must opt-in
    explicitly with ``dry_run=false``.
    """
    test_repo = _env("GITHUB_TEST_REPO", env)
    repo_value = (repo or "").strip()
    base = (base_branch or "").strip()
    branch = (branch_name or "").strip()
    title_value = (title or "").strip()
    pr_body = body or ""
    fp = (file_path or "").strip()

    # 1. token presence (we don't read the value here — only that it exists)
    if not _env("GITHUB_TOKEN", env):
        return GuardResult(allowed=False, reason="missing_github_token", repo=repo_value)

    # 2. opt-in flag
    if not _bool_env("RUN_REAL_GITHUB_TEST", env):
        return GuardResult(allowed=False, reason="run_real_github_test_not_true", repo=repo_value)

    # 3. sandbox repo pinned via env
    if not test_repo:
        return GuardResult(allowed=False, reason="missing_github_test_repo", repo=repo_value)

    # 4. repo must equal pinned sandbox repo
    if repo_value != test_repo:
        return GuardResult(
            allowed=False,
            reason="repo_mismatch",
            repo=repo_value,
            details={"expected": test_repo, "received": repo_value},
        )

    # 5. branch naming policy
    if not branch.startswith(ALLOWED_BRANCH_PREFIX):
        return GuardResult(
            allowed=False,
            reason="invalid_branch_prefix",
            repo=repo_value,
            details={"required_prefix": ALLOWED_BRANCH_PREFIX, "received": branch},
        )

    # 6. PR title naming policy
    if not title_value.startswith(ALLOWED_TITLE_PREFIX):
        return GuardResult(
            allowed=False,
            reason="invalid_title_prefix",
            repo=repo_value,
            details={"required_prefix": ALLOWED_TITLE_PREFIX, "received": title_value},
        )

    # 7. forbidden base branch
    if _base_branch_is_forbidden(base):
        return GuardResult(
            allowed=False,
            reason="production_base_branch",
            repo=repo_value,
            details={"received": base},
        )

    # 8. dry_run must be explicit False
    if dry_run is not False:
        return GuardResult(
            allowed=False,
            reason="dry_run_not_false",
            repo=repo_value,
            details={"received": dry_run},
        )

    # 9. file path scoping
    if not fp.startswith(ALLOWED_FILE_PREFIX):
        return GuardResult(
            allowed=False,
            reason="invalid_file_path",
            repo=repo_value,
            details={"required_prefix": ALLOWED_FILE_PREFIX, "received": fp},
        )

    # 10. file content markers (task_id / workflow_id / safety markers)
    missing_markers = [m for m in REQUIRED_FILE_MARKERS if m not in (file_content or "")]
    if missing_markers:
        return GuardResult(
            allowed=False,
            reason="missing_file_markers",
            repo=repo_value,
            details={"missing": missing_markers},
        )

    # 11. PR body sections (Safety Notes is mandatory Stage 23 addition)
    missing_sections = [s for s in REQUIRED_PR_SECTIONS if s not in pr_body]
    if missing_sections:
        return GuardResult(
            allowed=False,
            reason="missing_pr_sections",
            repo=repo_value,
            details={"missing": missing_sections},
        )

    return GuardResult(allowed=True, repo=repo_value)
