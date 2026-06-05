"""GitHub sandbox real-write guard.

This guard SITS ON TOP of ``apps/github-automation/src/real_guard.py``
and adds Stage 32 pilot rails:

* ``repo`` must equal ``GITHUB_TEST_REPO`` AND must NOT equal the
  canonical production repo (``coolerh250/AI-Agents-SWD``) unless the
  pinned ``GITHUB_TEST_REPO`` itself opts in via a sandbox suffix
  (``-sandbox`` / ``_sandbox``) -- defence-in-depth against an operator
  accidentally pinning the production repo to ``GITHUB_TEST_REPO``.
* ``file_path`` must live under ``docs/github-real-test/`` (already
  enforced by the existing real_guard, asserted again here so the
  Stage 32 unit tests exercise it independently).
* ``file_path`` must NOT touch ``.github/``, ``infra/``,
  ``migrations/``, ``apps/``, ``shared/``, ``scripts/`` -- nothing that
  could mutate code, CI workflows, or production-shaped paths.
* No merge / no branch protection mutation / no release / no deployment.

The dataclass is uniform with the Discord guard's so the operations +
audit code can serialise both identically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

PRODUCTION_REPO = "coolerh250/AI-Agents-SWD"
SANDBOX_REPO_SUFFIXES = ("-sandbox", "_sandbox")
ALLOWED_FILE_PREFIX = "docs/github-real-test/"
ALLOWED_BRANCH_PREFIX = "ai-agents-test/"
ALLOWED_TITLE_PREFIX = "[AI-Agents-SWD Test]"

FORBIDDEN_REPO_PATHS = (
    ".github/",
    "infra/",
    "migrations/",
    "apps/",
    "shared/",
    "scripts/",
    "tests/",
    "docs/operations/",
)

FORBIDDEN_INTENTS = (
    "merge",
    "branch_protection",
    "release",
    "deployment",
    "delete_branch",
    "workflow_secret",
)

GITHUB_REQUIRED_ENV = (
    "GITHUB_TOKEN",
    "GITHUB_TEST_REPO",
    "RUN_REAL_GITHUB_TEST",
)


@dataclass
class GitHubSandboxGuardResult:
    allowed: bool
    reason: str = ""
    repo: str = ""
    branch: str = ""
    file_path: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "repo": self.repo,
            "branch": self.branch,
            "file_path": self.file_path,
            "details": self.details,
        }


def _env(name: str, env: dict[str, str] | None) -> str:
    src = env if env is not None else os.environ
    return (src.get(name, "") or "").strip()


def _bool_env(name: str, env: dict[str, str] | None) -> bool:
    return _env(name, env).lower() == "true"


def _looks_like_sandbox(repo: str) -> bool:
    lowered = (repo or "").strip().lower()
    return any(lowered.endswith(s) for s in SANDBOX_REPO_SUFFIXES)


def evaluate_real_github_sandbox_request(
    *,
    repo: str,
    branch_name: str = "",
    title: str = "",
    file_path: str = "",
    intent: str = "create_pr",
    dry_run: Any = False,
    env: dict[str, str] | None = None,
) -> GitHubSandboxGuardResult:
    """Evaluate every Stage 32 sandbox pre-condition.

    Returns the first failure as ``allowed=False`` with a structured
    reason. Callers convert that into HTTP 409 + audit event +
    ``real_github_guard_blocks_total`` increment.
    """
    repo_value = (repo or "").strip()
    branch_value = (branch_name or "").strip()
    title_value = (title or "").strip()
    file_value = (file_path or "").strip()

    test_repo = _env("GITHUB_TEST_REPO", env)

    if not _env("GITHUB_TOKEN", env):
        return GitHubSandboxGuardResult(
            allowed=False, reason="missing_github_token", repo=repo_value
        )
    if not _bool_env("RUN_REAL_GITHUB_TEST", env):
        return GitHubSandboxGuardResult(
            allowed=False, reason="run_real_github_test_not_true", repo=repo_value
        )
    if not test_repo:
        return GitHubSandboxGuardResult(
            allowed=False, reason="missing_github_test_repo", repo=repo_value
        )
    if not repo_value:
        return GitHubSandboxGuardResult(allowed=False, reason="repo_required", repo=repo_value)
    if repo_value != test_repo:
        return GitHubSandboxGuardResult(
            allowed=False,
            reason="repo_mismatch",
            repo=repo_value,
            details={"expected": test_repo, "received": repo_value},
        )
    # Defence-in-depth: even if GITHUB_TEST_REPO is set, it must not be
    # the production repo unless explicitly suffixed -sandbox/_sandbox.
    if repo_value == PRODUCTION_REPO and not _looks_like_sandbox(repo_value):
        return GitHubSandboxGuardResult(
            allowed=False,
            reason="production_repo_blocked",
            repo=repo_value,
            details={"production_repo": PRODUCTION_REPO},
        )
    if intent in FORBIDDEN_INTENTS:
        return GitHubSandboxGuardResult(
            allowed=False,
            reason=f"forbidden_intent:{intent}",
            repo=repo_value,
            details={"intent": intent},
        )
    if dry_run is not False:
        return GitHubSandboxGuardResult(
            allowed=False,
            reason="dry_run_not_false",
            repo=repo_value,
            details={"received": dry_run},
        )
    if branch_value and not branch_value.startswith(ALLOWED_BRANCH_PREFIX):
        return GitHubSandboxGuardResult(
            allowed=False,
            reason="invalid_branch_prefix",
            repo=repo_value,
            branch=branch_value,
            details={"required_prefix": ALLOWED_BRANCH_PREFIX, "received": branch_value},
        )
    if title_value and not title_value.startswith(ALLOWED_TITLE_PREFIX):
        return GitHubSandboxGuardResult(
            allowed=False,
            reason="invalid_title_prefix",
            repo=repo_value,
            details={"required_prefix": ALLOWED_TITLE_PREFIX, "received": title_value},
        )
    if file_value:
        if any(file_value.startswith(p) for p in FORBIDDEN_REPO_PATHS):
            return GitHubSandboxGuardResult(
                allowed=False,
                reason="forbidden_repo_path",
                repo=repo_value,
                file_path=file_value,
                details={"forbidden_prefixes": list(FORBIDDEN_REPO_PATHS)},
            )
        if not file_value.startswith(ALLOWED_FILE_PREFIX):
            return GitHubSandboxGuardResult(
                allowed=False,
                reason="invalid_file_path",
                repo=repo_value,
                file_path=file_value,
                details={"required_prefix": ALLOWED_FILE_PREFIX, "received": file_value},
            )
    return GitHubSandboxGuardResult(
        allowed=True,
        repo=repo_value,
        branch=branch_value,
        file_path=file_value,
    )
