"""Step 54.4 -- agent-specific threat model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"


def _model() -> dict:
    data = yaml.safe_load((SEC / "agent-threat-model.yaml").read_text(encoding="utf-8")) or {}
    return data["agentThreatModel"]


def test_not_production_ready() -> None:
    assert _model()["productionReady"] is False


def test_required_scenarios_covered() -> None:
    scenarios = {t["scenario"] for t in _model()["threats"]}
    for required in (
        "prompt_injection",
        "tool_misuse",
        "unauthorized_production_action",
        "human_approval_bypass",
        "secret_exfiltration",
        "github_write_future_risk",
        "argocd_sync_future_risk",
    ):
        assert required in scenarios


def test_existing_mitigations_enumerated() -> None:
    mit = set(_model()["existingMitigations"])
    assert "production_executed_flag" in mit
    assert "hard_safety_actions" in mit
    assert "no_github_write" in mit
    assert "no_deploy_or_sync" in mit


def test_remaining_blockers_listed() -> None:
    assert _model()["remainingBlockers"]
