"""Stage 35 -- no workspace write / no patch from real-LLM plan path.

Pins the structural guarantee: the real-LLM plan-only provider does
NOT touch the code workspace / code change artifact / PR draft tables
in any code path. This is a belt-and-braces structural check; the
runtime smoke is exercised by ``verify_real_llm_plan_only_pilot.sh``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.sdk.llm import LLMProviderError, RealLLMPlanOnlyProvider

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_plan_only_provider_module_does_not_import_code_workspace():
    text = (_REPO_ROOT / "shared" / "sdk" / "llm" / "plan_only_provider.py").read_text(
        encoding="utf-8"
    )
    assert "from shared.sdk.code_workspace" not in text
    assert "CodeWorkspaceStore" not in text


def test_plan_only_provider_module_does_not_import_pr_draft_store():
    text = (_REPO_ROOT / "shared" / "sdk" / "llm" / "plan_only_provider.py").read_text(
        encoding="utf-8"
    )
    # The Stage 28 store name -- any reference is a red flag.
    assert "PRDraftStore" not in text
    assert "pr_draft_artifacts" not in text
    assert "code_change_artifacts" not in text


def test_plan_only_provider_does_not_expose_a_patch_method():
    p = RealLLMPlanOnlyProvider(vendor="openai", env={})
    with pytest.raises(LLMProviderError):
        p.generate_patch_proposal(task_id="T")
    with pytest.raises(LLMProviderError):
        p.generate_test_plan(task_id="T")


def test_operations_plan_only_endpoint_does_not_create_workspace():
    text = (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )
    block_start = text.index("async def operations_llm_plan_only_for_task")
    block = text[block_start : block_start + 4000]
    assert "CodeWorkspaceStore" not in block
    assert "PRDraftStore" not in block
    assert "create_workspace" not in block
    assert "code_change_artifacts" not in block


def test_default_real_plan_only_proposal_type_is_plan_only():
    """The Stage 35 doc names the proposal_type used for plan-only
    proposals; pin the spelling so a future refactor cannot accidentally
    rename it to ``patch_proposal``.
    """
    doc = (_REPO_ROOT / "docs" / "operations" / "real-llm-plan-only-pilot.md").read_text(
        encoding="utf-8"
    )
    assert "development_plan_only" in doc
