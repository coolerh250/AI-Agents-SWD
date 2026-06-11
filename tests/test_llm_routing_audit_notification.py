"""Stage 38 -- routing audit decision_types + notification events documented."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_doc() -> str:
    return (_REPO_ROOT / "docs" / "operations" / "llm-model-routing.md").read_text(encoding="utf-8")


def test_docs_register_stage38_audit_decision_types():
    doc = _read_doc()
    for decision in (
        "llm_model_registry_seeded",
        "llm_agent_model_policy_created",
        "llm_model_routing_selected",
        "llm_model_routing_fallback_selected",
        "llm_model_routing_blocked",
        "llm_model_routing_budget_blocked",
        "llm_model_routing_human_approval_required",
        "llm_direct_model_selection_rejected",
    ):
        assert decision in doc, f"audit decision {decision} not documented"


def test_docs_register_stage38_notification_events():
    doc = _read_doc()
    for event in (
        "llm.routing_selected",
        "llm.routing_blocked",
        "llm.routing_human_approval_required",
        "llm.routing_budget_blocked",
    ):
        assert event in doc, f"notification event {event} not documented"


def test_real_discord_default_denylist_still_includes_llm():
    """Stage 32 default-deny stream filter must still cover llm.* events."""
    text = (_REPO_ROOT / "shared" / "sdk" / "notifications" / "real_delivery_policy.py").read_text(
        encoding="utf-8"
    )
    assert '"llm.*"' in text
    block_start = text.index("DEFAULT_REAL_DELIVERY_ALLOWLIST")
    block_end = text.index("DEFAULT_REAL_DELIVERY_DENYLIST")
    allow_block = text[block_start:block_end]
    for forbidden in (
        "llm.routing_selected",
        "llm.routing_blocked",
        "llm.routing_human_approval_required",
        "llm.routing_budget_blocked",
    ):
        assert forbidden not in allow_block
