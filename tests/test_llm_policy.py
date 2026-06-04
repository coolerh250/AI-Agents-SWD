"""Stage 30 — LLM safety policy tests."""

from __future__ import annotations

from shared.sdk.llm import (
    DEFAULT_POLICY_LIMITS,
    LLMDevelopmentPlan,
    LLMFileChange,
    LLMPatchProposal,
    LLMSafetyPolicy,
    LLMTestPlan,
    apply_llm_safety_policy,
)


def _ok_change() -> LLMFileChange:
    return LLMFileChange(
        file_path="docs/generated/notes.md",
        change_type="create",
        proposed_content="ok content\n",
        diff_summary="add notes",
        reason="ok",
    )


def test_policy_allows_clean_proposal() -> None:
    prop = LLMPatchProposal(task_id="t1", changes=[_ok_change()])
    res = apply_llm_safety_policy(prop)
    assert res["allowed"] is True
    assert res["violations"] == []
    assert res["requires_human_review"] is True
    assert res["limits"] == DEFAULT_POLICY_LIMITS


def test_policy_blocks_denied_path() -> None:
    prop = LLMPatchProposal(
        task_id="t1",
        changes=[
            LLMFileChange(
                file_path="infra/docker-compose/docker-compose.yml",
                change_type="update",
                proposed_content="services: {}\n",
            )
        ],
    )
    res = apply_llm_safety_policy(prop)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "path_blocked" in rules


def test_policy_blocks_delete_change_type() -> None:
    prop = LLMPatchProposal(
        task_id="t1",
        changes=[
            LLMFileChange(
                file_path="docs/generated/oops.md",
                change_type="delete",
            )
        ],
    )
    res = apply_llm_safety_policy(prop)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "change_type_blocked" in rules


def test_policy_blocks_secret_like_content() -> None:
    prop = LLMPatchProposal(
        task_id="t1",
        changes=[
            LLMFileChange(
                file_path="docs/generated/oops.md",
                change_type="create",
                proposed_content="token = ghp_" + "A" * 40,
            )
        ],
    )
    res = apply_llm_safety_policy(prop)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "secret_like_content" in rules


def test_policy_blocks_destructive_command() -> None:
    prop = LLMPatchProposal(
        task_id="t1",
        changes=[
            LLMFileChange(
                file_path="apps/demo-generated/wipe.py",
                change_type="create",
                proposed_content="import os\nos.system('rm -rf /')\n",
            )
        ],
    )
    res = apply_llm_safety_policy(prop)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "destructive_content" in rules


def test_policy_blocks_too_many_files() -> None:
    changes = [
        LLMFileChange(
            file_path=f"docs/generated/x{i}.md", change_type="create", proposed_content="x"
        )
        for i in range(10)
    ]
    prop = LLMPatchProposal(task_id="t1", changes=changes)
    res = apply_llm_safety_policy(prop)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "too_many_files" in rules


def test_policy_blocks_content_too_large() -> None:
    big = "x" * (DEFAULT_POLICY_LIMITS["max_content_chars_per_file"] + 1)
    prop = LLMPatchProposal(
        task_id="t1",
        changes=[
            LLMFileChange(
                file_path="docs/generated/big.md", change_type="create", proposed_content=big
            )
        ],
    )
    res = apply_llm_safety_policy(prop)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "content_too_large" in rules


def test_policy_warns_on_low_confidence_but_still_allows() -> None:
    prop = LLMPatchProposal(task_id="t1", changes=[_ok_change()], confidence=0.3)
    res = apply_llm_safety_policy(prop)
    assert res["allowed"] is True
    assert any("low_confidence" in w for w in res["warnings"])


def test_policy_blocks_development_plan_with_secret_in_summary() -> None:
    plan = LLMDevelopmentPlan(
        task_id="t1",
        summary="here is a leaked sk-" + "A" * 40,
    )
    res = apply_llm_safety_policy(plan)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "secret_like_content" in rules


def test_policy_blocks_test_plan_with_destructive_step() -> None:
    plan = LLMTestPlan(
        task_id="t1",
        manual_tests=["run `rm -rf /tmp/x` and observe"],
    )
    res = apply_llm_safety_policy(plan)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "destructive_content" in rules


def test_policy_returns_schema_invalid_for_none() -> None:
    res = apply_llm_safety_policy(None)  # type: ignore[arg-type]
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "schema_invalid" in rules


def test_policy_warning_on_files_to_consider_outside_allowlist() -> None:
    plan = LLMDevelopmentPlan(
        task_id="t1",
        files_to_consider=["infra/docker-compose/docker-compose.yml"],
        confidence=0.9,
    )
    res = apply_llm_safety_policy(plan)
    # plan-level: warnings only — plans don't write files.
    assert any("file_listed_but_blocked" in w for w in res["warnings"])


def test_policy_custom_limit_overrides_defaults() -> None:
    pol = LLMSafetyPolicy(max_files_changed=1)
    prop = LLMPatchProposal(
        task_id="t1",
        changes=[_ok_change(), _ok_change()],
    )
    res = apply_llm_safety_policy(prop, policy=pol)
    assert res["allowed"] is False
    rules = {v["rule"] for v in res["violations"]}
    assert "too_many_files" in rules


def test_policy_always_returns_requires_human_review_true() -> None:
    prop = LLMPatchProposal(task_id="t1", changes=[_ok_change()])
    res = apply_llm_safety_policy(prop)
    assert res["requires_human_review"] is True
