"""Step 57 -- work-item decomposition policy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "infra" / "delivery" / "work-item-decomposition-policy.yaml"


def _p() -> dict:
    return (yaml.safe_load(POLICY.read_text(encoding="utf-8")) or {})["workItemDecompositionPolicy"]


def test_deterministic_no_llm() -> None:
    p = _p()
    assert p["deterministicOnly"] is True
    assert p["llmUsed"] is False
    assert p["productionReady"] is False


def test_types_defined_with_required_fields() -> None:
    types = _p()["types"]
    for t in (
        "epic",
        "feature",
        "task",
        "bug",
        "security_task",
        "ops_task",
        "research_task",
        "verification_task",
        "release_task",
    ):
        assert t in types
        for field in ("allowedTargets", "defaultApprovalRequired", "productionEffectDefault"):
            assert field in types[t]
        assert types[t]["productionEffectDefault"] is False


def test_release_task_requires_linkage() -> None:
    assert _p()["types"]["release_task"]["deliveryPackageLinkageRequired"] is True
