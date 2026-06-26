"""Step 58 -- operational metrics model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "infra" / "operations" / "operational-metrics-model.yaml"


def _m() -> dict:
    return (yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {})["operationalMetrics"]


def test_production_ready_false_and_domains() -> None:
    m = _m()
    assert m["productionReady"] is False
    assert {
        "delivery",
        "work_items",
        "dispatch",
        "agents",
        "workflows",
        "runtime",
        "gitops",
        "security",
        "approval",
        "audit",
        "safety",
    } <= set(m["domains"])


def test_visibility_only_rules() -> None:
    rules = _m()["rules"]
    for r in (
        "metricsAreVisibilityOnly",
        "metricsAreNotProductionApproval",
        "missingDataMustNotBeHidden",
        "doesNotClaimProductionReadiness",
        "doesNotClaimSlaGuarantee",
    ):
        assert rules[r] is True
