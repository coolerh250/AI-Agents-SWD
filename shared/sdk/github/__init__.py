"""GitHub SDK — dry-run-by-default REST client for the AI Agents SWD Platform."""

from shared.sdk.github.client import GitHubClient
from shared.sdk.github.errors import (
    GitHubAuthError,
    GitHubClientError,
    GitHubMissingTokenError,
    GitHubNotFoundError,
)
from shared.sdk.github.models import (
    GitHubBranch,
    GitHubChecks,
    GitHubFile,
    GitHubIssue,
    GitHubPullRequest,
)

__all__ = [
    "GitHubClient",
    "GitHubClientError",
    "GitHubMissingTokenError",
    "GitHubAuthError",
    "GitHubNotFoundError",
    "GitHubIssue",
    "GitHubBranch",
    "GitHubFile",
    "GitHubPullRequest",
    "GitHubChecks",
]
