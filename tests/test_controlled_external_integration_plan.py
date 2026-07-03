"""Step 65B -- Controlled staging external integration plan (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
PLAN = STAGING / "controlled-external-integration-plan.md"
SECRET = STAGING / "staging-secret-backend-plan.md"
GITHUB = STAGING / "github-sandbox-integration-plan.md"
NOTIF = STAGING / "notification-staging-channel-plan.md"
LLM = STAGING / "llm-staging-integration-plan.md"
DEFERRED = STAGING / "deferred-integration-register.md"
GATES = STAGING / "external-integration-authorization-gates.md"
CHECKLIST = STAGING / "external-integration-user-input-checklist.md"
RISKS = STAGING / "external-integration-risk-register.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (PLAN, SECRET, GITHUB, NOTIF, LLM, DEFERRED, GATES, CHECKLIST, RISKS)
IN_SCOPE = (
    "github sandbox",
    "notification staging channel",
    "llm staging key",
    "staging secret backend",
)
GATE_STEPS = ("65c", "65d", "65e", "65f", "65g", "65h", "65i")


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_in_scope_integrations_documented() -> None:
    low = PLAN.read_text(encoding="utf-8").lower()
    for item in IN_SCOPE:
        assert item in low, item


def test_deferred_integrations_documented() -> None:
    low = DEFERRED.read_text(encoding="utf-8").lower()
    assert "container registry" in low and "defer" in low
    assert "cloud storage" in low or "google drive" in low


def test_authorization_gates_documented() -> None:
    low = GATES.read_text(encoding="utf-8").lower()
    for step in GATE_STEPS:
        assert step in low, step


def test_user_input_checklist_documented() -> None:
    low = CHECKLIST.read_text(encoding="utf-8").lower()
    assert "needed later" in low
    assert "not to be provided" in low


def test_no_integration_enablement_or_external_write() -> None:
    combined = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "no integration enabled" in combined
    assert "no runtime change" in combined
    for p in DOCS:
        low = p.read_text(encoding="utf-8").lower()
        assert "no production action" in low, p.name
        assert "no external write" in low, p.name
        assert "production_executed_true_count=0" in low, p.name


def test_no_secret_values_stored() -> None:
    shapes = re.compile(r"(-----BEGIN|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{10,})")
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert not shapes.search(text), p.name
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE), p.name


def test_safety_flags_present() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text


def test_step65b_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65B" in text
    assert "CONTROLLED_EXTERNAL_INTEGRATION_PLAN_VERIFY" in text
