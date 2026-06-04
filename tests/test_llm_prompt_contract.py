"""Stage 30 — prompt contract + redaction tests."""

from __future__ import annotations

from shared.sdk.llm import (
    PROMPT_CONTRACT_VERSION,
    build_prompt_contract,
    hash_text,
    redact_text,
)


def test_prompt_contract_has_version_and_safety_rails() -> None:
    contract = build_prompt_contract(
        task_id="t1",
        execution_mode="delivery_task",
        interaction_type="patch_proposal",
        description="please add /healthz API",
        allowed_paths=["docs/generated/"],
        denied_paths=["infra/*"],
        output_schema_name="LLMPatchProposal",
    )
    assert contract["contract_version"] == PROMPT_CONTRACT_VERSION
    rails = contract["safety_rails"]
    assert rails["production_executed"] is False
    assert rails["no_secrets"] is True
    assert rails["no_delete"] is True
    assert rails["no_production_deploy"] is True
    assert rails["must_mark_requires_human_review_true"] is True
    assert contract["output_schema"] == "LLMPatchProposal"


def test_prompt_contract_does_not_leak_api_key_in_summary() -> None:
    contract = build_prompt_contract(
        task_id="t1",
        execution_mode="delivery_task",
        interaction_type="development_plan",
        description="please add api OPENAI_API_KEY=sk-" + "A" * 40,
        allowed_paths=["docs/generated/"],
        denied_paths=["infra/*"],
        output_schema_name="LLMDevelopmentPlan",
    )
    # task_summary is the prompt-going content. We did NOT redact it at
    # build time — that's the producer's job via redact_text() when
    # persisting the preview — but the description must NEVER end up
    # in a safety_rails or instructions key.
    assert "sk-" + "A" * 40 not in contract["instructions"]
    # The producer must redact before persistence — verified below.
    preview = redact_text(contract["task_summary"])
    assert "sk-" + "A" * 40 not in preview


def test_hash_text_is_stable_and_hex() -> None:
    a = hash_text("hello")
    b = hash_text("hello")
    assert a == b
    assert len(a) == 64
    int(a, 16)  # raises if not hex


def test_hash_text_changes_with_content() -> None:
    assert hash_text("hello") != hash_text("hello!")


def test_redact_text_masks_github_token() -> None:
    out = redact_text("token = ghp_" + "A" * 40)
    assert "ghp_" + "A" * 40 not in out
    assert "[REDACTED:github_token]" in out


def test_redact_text_masks_openai_key() -> None:
    out = redact_text("export OPENAI_API_KEY=sk-" + "A" * 40)
    assert "[REDACTED]" in out
    assert "sk-" + "A" * 40 not in out


def test_redact_text_masks_anthropic_key() -> None:
    out = redact_text("ANTHROPIC_API_KEY=sk-ant-" + "A" * 30)
    assert "[REDACTED]" in out
    assert "sk-ant-" + "A" * 30 not in out


def test_redact_text_truncates_long_input() -> None:
    big = "x" * 5000
    out = redact_text(big, limit=100)
    assert len(out) <= 120
    assert out.endswith("…[truncated]")


def test_redact_text_handles_private_key_marker() -> None:
    body = "-----BEGIN RSA PRIVATE KEY-----\nABC123\n-----END RSA PRIVATE KEY-----"
    out = redact_text(body)
    assert "[REDACTED:private_key]" in out


def test_prompt_contract_records_acceptance_criteria() -> None:
    contract = build_prompt_contract(
        task_id="t1",
        execution_mode="delivery_task",
        interaction_type="development_plan",
        description="please add api",
        allowed_paths=["docs/generated/"],
        denied_paths=["infra/*"],
        output_schema_name="LLMDevelopmentPlan",
        acceptance_criteria=["healthz returns 200", "tests pass"],
    )
    assert contract["acceptance_criteria"] == ["healthz returns 200", "tests pass"]
