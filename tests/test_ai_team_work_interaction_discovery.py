"""Step 66A.1 -- AI Agents Team Work interaction discovery (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "interaction-discovery": TEST / "ai-team-work-interaction-model-discovery.md",
    "current-gap-analysis": TEST / "ai-team-work-current-gap-analysis.md",
    "user-role-model": TEST / "ai-team-work-user-role-model.md",
    "task-type-taxonomy": TEST / "ai-team-work-task-type-taxonomy.md",
    "multi-channel-intake": TEST / "ai-team-work-multi-channel-intake-model.md",
    "clarification-model": TEST / "ai-team-work-agent-clarification-model.md",
    "delivery-acceptance": TEST / "ai-team-work-delivery-acceptance-model.md",
    "agent-team-model": TEST / "ai-team-work-agent-team-model.md",
    "lifecycle-notification": TEST / "ai-team-work-lifecycle-notification-model.md",
    "operator-action-center": TEST / "ai-team-work-operator-action-center-model.md",
    "web-research-capability": TEST / "ai-team-work-web-research-capability-model.md",
    "decision-register": TEST / "ai-team-work-decision-register.md",
    "step66-roadmap": TEST / "ai-team-work-step66-roadmap-proposal.md",
}


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values()).lower()


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_six_operator_decisions_integrated() -> None:
    low = _all_low()
    for token in (
        "multi-role",
        "intake",
        "clarification",
        "accept",
        "fixed software delivery team",
    ):
        assert token in low, token


def test_decision_register_d1_to_d14() -> None:
    reg = DOCS["decision-register"].read_text(encoding="utf-8").lower()
    for i in range(1, 15):
        assert f"d{i}" in reg, f"D{i}"


def test_required_domains_covered() -> None:
    low = _all_low()
    for t in (
        "role",
        "task type",
        "multi-channel intake",
        "clarification",
        "delivery inbox",
        "acceptance",
        "agent team",
        "notification",
        "operator action center",
        "web research",
    ):
        assert t in low, t


def test_action_center_addresses_step65_gaps() -> None:
    oac = DOCS["operator-action-center"].read_text(encoding="utf-8").lower()
    assert "dlq" in oac and "approval" in oac


def test_web_research_flagged_future() -> None:
    web = DOCS["web-research-capability"].read_text(encoding="utf-8").lower()
    assert "missing" in web or "future connector" in web


def test_recommendations_non_final() -> None:
    assert "non-final" in _all_low()


def test_planning_only_posture() -> None:
    low = _all_low()
    assert "no ui implementation" in low or "no ui was implemented" in low
    assert "no workflow" in low
    assert "no external action" in low
    assert "no production action" in low


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
