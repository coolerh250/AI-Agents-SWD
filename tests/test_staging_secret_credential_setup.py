"""Step 65C -- Staging secret & credential setup (docs + no-secret posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-secret-credential-setup-report.md"
REFMAP = STAGING / "staging-secret-reference-map.md"
KILLSWITCH = STAGING / "staging-secret-kill-switch-record.md"
VALIDATION = STAGING / "staging-secret-validation-result.md"
GAPS = STAGING / "staging-secret-known-gaps.md"
HANDBACK = STAGING / "staging-secret-operator-handback.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, REFMAP, KILLSWITCH, VALIDATION, GAPS, HANDBACK)
SAFE_FLAGS = (
    "github_dry_run=true",
    "run_real_github_test=false",
    "run_real_discord_test=false",
    "enable_real_llm_network_call=false",
    "llm_provider=mock",
)
NO_ACTIONS = (
    "no github write",
    "no notification send",
    "no llm call",
    "no workflow execution",
    "no production action",
)
SECRET_SHAPES = re.compile(
    r"(-----BEGIN|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_secret_references_documented() -> None:
    low = REFMAP.read_text(encoding="utf-8").lower()
    assert "github_token" in low
    assert "discord_bot_token" in low
    assert "anthropic_api_key" in low or "llm_api_key" in low


def test_secret_backend_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "env-file" in low


def test_safe_kill_switches_documented() -> None:
    low = KILLSWITCH.read_text(encoding="utf-8").lower()
    for flag in SAFE_FLAGS:
        assert flag in low, flag


def test_no_live_actions_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    for phrase in NO_ACTIONS:
        assert phrase in low, phrase


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert not SECRET_SHAPES.search(text), p.name
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE), p.name
        assert not re.search(
            r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{12,}",
            text,
            re.IGNORECASE,
        ), p.name


def test_no_production_action_and_prod_exec_zero() -> None:
    for p in DOCS:
        low = p.read_text(encoding="utf-8").lower()
        assert "no production action" in low, p.name
        assert "production_executed_true_count=0" in low, p.name


def test_safety_flags_present() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text


def test_step65c_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65C" in text
    assert "STAGING_SECRET_CREDENTIAL_SETUP_VERIFY" in text
