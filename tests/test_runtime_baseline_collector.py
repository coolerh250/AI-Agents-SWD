"""Step 51.4 -- runtime baseline collector + committed-summary anti-drift."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.runtime_baseline import (
    build_runtime_baseline_summary,
    load_runtime_baseline_summary,
)

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "infra" / "kubernetes" / "runtime-baseline-summary.yaml"


def test_committed_summary_matches_collected() -> None:
    collected = build_runtime_baseline_summary(ROOT)
    committed = yaml.safe_load(SUMMARY.read_text(encoding="utf-8"))
    assert committed == collected, "runtime-baseline-summary.yaml is stale; regenerate it"


def test_status_validated_not_deployed() -> None:
    s = load_runtime_baseline_summary(SUMMARY)
    assert s is not None
    assert s["status"] == "validated_not_deployed"
    assert s["clusterConnected"] is False


def test_safety_facts_all_safe() -> None:
    s = load_runtime_baseline_summary(SUMMARY)
    assert s is not None
    facts = s["safetyFacts"]
    assert facts["hostPathPresent"] is False
    assert facts["privilegedWorkloadPresent"] is False
    assert facts["clusterAdminPresent"] is False
    assert facts["serviceAccountTokenMounted"] is False
    assert facts["embeddedSecretDetected"] is False
    assert facts["defaultDenyEnabled"] is True
    assert facts["externalEgressEnabled"] is False


def test_all_areas_passed() -> None:
    s = load_runtime_baseline_summary(SUMMARY)
    assert s is not None
    for area, status in s["areaStatus"].items():
        assert status == "passed", area


def test_missing_summary_returns_none() -> None:
    assert load_runtime_baseline_summary(ROOT / "infra" / "kubernetes" / "nope.yaml") is None
