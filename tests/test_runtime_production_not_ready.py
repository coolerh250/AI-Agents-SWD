"""Step 51.4 -- runtime baseline never declares production readiness."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.runtime_baseline import (
    load_runtime_baseline_summary,
    runtime_baseline_safety_fields,
)

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "infra" / "kubernetes" / "runtime-baseline-summary.yaml"


def test_production_safety_not_ready() -> None:
    s = load_runtime_baseline_summary(SUMMARY)
    assert s is not None
    prod = s["productionSafety"]
    assert prod["productionReady"] is False
    assert prod["realDeployEnabled"] is False
    assert prod["productionApplicationEnabled"] is False
    assert prod["autoSyncEnabled"] is False
    assert prod["validatedNotDeployed"] is True


def test_safety_fields_production_not_ready() -> None:
    f = runtime_baseline_safety_fields(load_runtime_baseline_summary(SUMMARY))
    assert f["runtime_production_ready"] is False
    assert f["runtime_validated_not_deployed"] is True


def test_status_is_not_production_ready() -> None:
    s = load_runtime_baseline_summary(SUMMARY)
    assert s is not None
    assert s["status"] != "production_ready"
    assert s["status"] in ("validated_not_deployed", "passed_with_non_production_limitations")
