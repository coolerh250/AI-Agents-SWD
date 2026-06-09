"""Stage 35 -- audit decision_types + notification events documented."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_docs_register_stage35_audit_decision_types():
    doc = (_REPO_ROOT / "docs" / "operations" / "llm-cost-governance.md").read_text(
        encoding="utf-8"
    )
    for decision in (
        "llm_budget_policy_created",
        "llm_budget_preflight_allowed",
        "llm_budget_exceeded",
        "llm_real_plan_created",
        "llm_plan_blocked_by_policy",
        "llm_real_test_skipped",
    ):
        assert decision in doc, f"audit decision {decision} not documented"


def test_docs_register_stage35_notification_events():
    doc = (_REPO_ROOT / "docs" / "operations" / "llm-cost-governance.md").read_text(
        encoding="utf-8"
    )
    for event in (
        "llm.plan_ready_for_review",
        "llm.budget_exceeded",
        "llm.real_test_skipped",
        "llm.plan_blocked_by_policy",
    ):
        assert event in doc, f"notification event {event} not documented"


def test_real_discord_default_denylist_still_includes_llm():
    """Stage 33 default-deny policy includes ``llm.*`` -- Stage 35 must
    NOT silently widen the default allowlist to include any of the new
    Stage 35 events.
    """
    text = (_REPO_ROOT / "shared" / "sdk" / "notifications" / "real_delivery_policy.py").read_text(
        encoding="utf-8"
    )
    assert '"llm.*"' in text
    # And the default allowlist must NOT carry any llm.* event.
    block_start = text.index("DEFAULT_REAL_DELIVERY_ALLOWLIST")
    block_end = text.index("DEFAULT_REAL_DELIVERY_DENYLIST")
    allow_block = text[block_start:block_end]
    assert "llm.plan_ready_for_review" not in allow_block
    assert "llm.budget_exceeded" not in allow_block
