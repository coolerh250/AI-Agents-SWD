"""Errors raised by the GitHub SDK.

We funnel every failure through GitHubClientError so callers can render a
single, secret-free error path. The original cause (httpx error, GitHub
4xx/5xx body, etc.) is preserved on ``__cause__`` but the message we ship
never includes the token.
"""

from __future__ import annotations


class GitHubClientError(RuntimeError):
    """Raised for any failure the GitHub SDK chooses to surface."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        operation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.operation = operation


class GitHubMissingTokenError(GitHubClientError):
    """Raised when dry_run=False but GITHUB_TOKEN is not set."""


class GitHubAuthError(GitHubClientError):
    """Raised when GitHub returns 401 / 403."""


class GitHubNotFoundError(GitHubClientError):
    """Raised when GitHub returns 404."""
