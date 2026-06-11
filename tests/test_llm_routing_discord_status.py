"""Stage 38 -- Discord task status surfaces routing fields."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_main() -> str:
    return (_REPO_ROOT / "apps" / "discord-gateway" / "src" / "main.py").read_text(encoding="utf-8")


def test_discord_task_lookup_carries_routing_fields():
    src = _read_main()
    for field in (
        '"llm_model_router_enabled": True',
        '"agent_direct_model_selection_allowed": False',
        '"selected_model_alias"',
        '"selected_provider"',
        '"selected_model_tier"',
        '"routing_decision"',
        '"routing_requires_human_review"',
        '"routing_fallback_used"',
    ):
        assert field in src, f"missing discord field: {field}"


def test_discord_endpoint_pulls_routing_from_llm_assistance():
    src = _read_main()
    assert "routing_decisions" in src
