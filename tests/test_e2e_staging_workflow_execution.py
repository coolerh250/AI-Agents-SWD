"""Step 65G.2 -- Controlled E2E staging workflow execution (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "e2e-staging-workflow-execution-report.md"
EVIDENCE = STAGING / "e2e-staging-workflow-evidence.md"
PIPELINE = STAGING / "e2e-staging-agent-pipeline-record.md"
LLM = STAGING / "e2e-staging-llm-record.md"
GITHUB = STAGING / "e2e-staging-github-record.md"
DISCORD = STAGING / "e2e-staging-discord-record.md"
CHECKLIST = STAGING / "e2e-staging-admin-console-evidence-checklist.md"
RESET = STAGING / "e2e-staging-safety-reset-record.md"
GAPS = STAGING / "e2e-staging-known-gaps.md"
VALIDATION = STAGING / "e2e-staging-operator-validation-request.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, EVIDENCE, PIPELINE, LLM, GITHUB, DISCORD, CHECKLIST, RESET, GAPS, VALIDATION)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_fresh_intake_documented() -> None:
    low = _all_low()
    assert "fresh intake" in low
    assert "step65g2-e2e-20260706074202" in low


def test_agent_pipeline_documented() -> None:
    low = _all_low()
    assert "intake-agent" in low and "devops-agent" in low
    assert "5 hops" in low or "5-hop" in low


def test_github_sandbox_output_documented() -> None:
    low = _all_low()
    assert "pr #16" in low or "pull/16" in low
    assert "ai-agents-swd-sandbox" in low
    assert "merge_performed=false" in low or "no merge" in low


def test_discord_staging_output_documented() -> None:
    low = _all_low()
    assert "mysanbox" in low and "#general" in low
    assert "[staging]" in low
    assert "external_sent" in low


def test_llm_audited_call_documented() -> None:
    low = _all_low()
    assert "external_anthropic" in low
    assert "budget/audit" in low
    assert "0.05073" in low


def test_no_direct_diagnostic_calls() -> None:
    low = _all_low()
    assert "direct diagnostic" in low
    assert "**0**" in low or "0 direct diagnostic" in low


def test_no_production_action() -> None:
    assert "no production action" in _all_low()


def test_reset_documented() -> None:
    low = _all_low()
    assert "reset" in low
    assert "sandbox_github_draft_pr_live_mode_enabled=false" in low


def test_operator_validation_pending() -> None:
    low = _all_low()
    assert "operator ui validation" in low or "operator validation" in low
    assert "pending" in low


def test_no_secret_values_stored() -> None:
    shapes = re.compile(
        r"(-----BEGIN|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,}|"
        r"MT[IMQ][A-Za-z0-9_.-]{20,})"
    )
    tok = re.compile(r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I)
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert not shapes.search(text), p.name
        assert not tok.search(text), p.name
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE), p.name


def test_prod_exec_zero_documented() -> None:
    low = _all_low()
    assert "production_executed_true_count=0" in low
    assert not re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low)


def test_progress_documents_stage() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65G.2" in text
    assert "E2E_STAGING_WORKFLOW_EXECUTION_VERIFY" in text
