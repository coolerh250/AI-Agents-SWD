"""Stage 32 -- Real-integration sandbox guards.

The platform's external surfaces (real Discord, real GitHub) MUST pass
through the dataclasses + evaluator functions in this module before any
external API call is made. Each guard is pure (no I/O, no env mutation)
so the same evaluation can be unit-tested, replayed in audit, and
inspected via the operations view.

The two surfaces share the same shape (allowed / reason / details /
to_safe_dict) so callers can serialise + audit them uniformly. Neither
guard ever reads, returns, or logs a token value.
"""

from __future__ import annotations

from .discord import (
    DISCORD_REQUIRED_ENV,
    DiscordRealGuardResult,
    evaluate_real_discord_request,
    render_safe_discord_message,
)
from .github import (
    GITHUB_REQUIRED_ENV,
    FORBIDDEN_REPO_PATHS,
    GitHubSandboxGuardResult,
    evaluate_real_github_sandbox_request,
)
from .inputs import collect_real_integration_inputs

__all__ = [
    "DISCORD_REQUIRED_ENV",
    "GITHUB_REQUIRED_ENV",
    "FORBIDDEN_REPO_PATHS",
    "DiscordRealGuardResult",
    "GitHubSandboxGuardResult",
    "collect_real_integration_inputs",
    "evaluate_real_discord_request",
    "evaluate_real_github_sandbox_request",
    "render_safe_discord_message",
]
