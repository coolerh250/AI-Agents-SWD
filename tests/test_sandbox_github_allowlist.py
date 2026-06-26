"""Step 59 -- sandbox repository allowlist resolution."""

from __future__ import annotations

from shared.sdk.sandbox_github import allowlist


def test_known_key_resolves() -> None:
    repo = allowlist.resolve_repository("ai-agents-sandbox")
    assert repo is not None
    assert repo.sandbox_only is True
    assert repo.allow_merge is False
    assert repo.allow_draft_pr is True
    assert "main" in repo.allowed_base_branches
    assert any(p.startswith("sandbox/ai-agents/") for p in repo.allowed_head_prefixes)


def test_unknown_key_does_not_resolve() -> None:
    assert allowlist.resolve_repository("nope") is None
    assert allowlist.resolve_repository("") is None
    assert allowlist.resolve_repository("../../etc/passwd") is None


def test_base_branch_and_head_prefix_checks() -> None:
    repo = allowlist.resolve_repository("ai-agents-sandbox")
    assert repo is not None
    assert allowlist.base_branch_allowed(repo, "main") is True
    assert allowlist.base_branch_allowed(repo, "production") is False
    assert allowlist.head_prefix_allowed(repo, "sandbox/ai-agents/x/y/z") is True
    assert allowlist.head_prefix_allowed(repo, "feature/x") is False
