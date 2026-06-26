"""Step 58 -- operational metrics source inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "infra" / "operations" / "operational-metrics-source-inventory.yaml"


def _inv() -> dict:
    return (yaml.safe_load(INV.read_text(encoding="utf-8")) or {})[
        "operationalMetricsSourceInventory"
    ]


def test_sources_declared_with_required_fields() -> None:
    inv = _inv()
    assert inv["productionReady"] is False
    names = {s["name"] for s in inv["sources"]}
    assert {"projects", "project_work_items", "work_item_dispatches", "operations_safety"} <= names
    for s in inv["sources"]:
        assert {"name", "type", "freshness", "availability"} <= set(s)
        assert s["secretExposureRisk"] is False


def test_missing_runtime_shown_as_stale() -> None:
    rules = _inv()["rules"]
    assert rules["missingRuntimeReportShownAsStale"] is True
    assert rules["runtimeReportsNeverCommitted"] is True
    assert rules["noArbitraryPath"] is True
    assert rules["noSecretExposure"] is True
