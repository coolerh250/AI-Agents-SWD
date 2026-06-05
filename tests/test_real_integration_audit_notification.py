"""Stage 32 -- assert the audit decision_types + notification events.

Pure structural assertions on the discord-gateway + github-automation
source so a future refactor cannot silently rename a Stage 32 marker
the operator view + verify scripts rely on.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

DISCORD_DECISION_TYPES = (
    "discord_real_test_sent",
    "discord_real_test_blocked",
    "discord_real_task_received",
    "discord_real_task_blocked",
)
DISCORD_EVENT_TYPES = (
    "discord.real_test_sent",
    "discord.real_task_received",
)
GITHUB_DECISION_TYPES = (
    "github_sandbox_pr_created",
    "github_sandbox_guard_failed",
)
GITHUB_EVENT_TYPES = ("github.sandbox_pr.created",)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_discord_gateway_emits_stage32_audit_decisions():
    src = _read(_REPO_ROOT / "apps" / "discord-gateway" / "src" / "main.py")
    for decision in DISCORD_DECISION_TYPES:
        assert decision in src, f"discord-gateway missing decision_type={decision}"


def test_discord_gateway_emits_stage32_notification_events():
    src = _read(_REPO_ROOT / "apps" / "discord-gateway" / "src" / "main.py")
    for event in DISCORD_EVENT_TYPES:
        assert event in src, f"discord-gateway missing event_type={event}"


def test_github_automation_emits_stage32_audit_decisions():
    src = _read(_REPO_ROOT / "apps" / "github-automation" / "src" / "main.py")
    for decision in GITHUB_DECISION_TYPES:
        assert decision in src, f"github-automation missing decision_type={decision}"


def test_github_automation_emits_stage32_notification_event():
    src = _read(_REPO_ROOT / "apps" / "github-automation" / "src" / "main.py")
    for event in GITHUB_EVENT_TYPES:
        assert event in src, f"github-automation missing event_type={event}"


def test_operations_view_lists_stage32_decision_types():
    src = _read(_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py")
    for decision in DISCORD_DECISION_TYPES + GITHUB_DECISION_TYPES:
        assert decision in src, f"operations.py missing decision_type={decision}"


def test_artifact_refs_carry_production_executed_false():
    src = _read(_REPO_ROOT / "apps" / "github-automation" / "src" / "main.py")
    assert '"production_executed": False' in src
    src = _read(_REPO_ROOT / "apps" / "discord-gateway" / "src" / "main.py")
    assert '"production_executed": False' in src
