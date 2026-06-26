"""Step 59 -- sandbox draft branch naming policy."""

from __future__ import annotations

import pytest

from shared.sdk.sandbox_github import branch


def test_generated_branch_is_sandbox_prefixed_and_clean() -> None:
    name = branch.generate_branch_name("Demo Project", "WI-0007", "abcdef123456ZZZ")
    assert name.startswith("sandbox/ai-agents/")
    assert " " not in name
    assert ".." not in name
    assert not any(c in name for c in ";|&$`()<>\\")


def test_hostile_inputs_are_sanitized() -> None:
    name = branch.generate_branch_name("../../etc", "wi; rm -rf /", "$(whoami)")
    assert ".." not in name
    assert not any(c in name for c in ";|&$`()<>\\ ")
    assert name.startswith("sandbox/ai-agents/")


def test_protected_and_prefixed_branches_rejected() -> None:
    for bad in ("main", "production", "release"):
        with pytest.raises(branch.BranchPolicyError):
            branch.validate_branch_name(bad)
    with pytest.raises(branch.BranchPolicyError):
        branch.validate_branch_name("sandbox/ai-agents/production/x/y")


def test_non_sandbox_prefix_rejected() -> None:
    with pytest.raises(branch.BranchPolicyError):
        branch.validate_branch_name("feature/foo")
