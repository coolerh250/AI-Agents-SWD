"""Step 54.4 -- supply-chain threat model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"


def _model() -> dict:
    data = (
        yaml.safe_load((SEC / "supply-chain-threat-model.yaml").read_text(encoding="utf-8")) or {}
    )
    return data["supplyChainThreatModel"]


def test_not_production_ready() -> None:
    assert _model()["productionReady"] is False


def test_required_scenarios_covered() -> None:
    scenarios = {t["scenario"] for t in _model()["threats"]}
    for required in (
        "dependency_compromise",
        "missing_python_lockfile",
        "docker_base_image_compromise",
        "mutable_tag",
        "missing_image_digest",
        "root_container",
        "missing_sbom",
        "missing_image_vulnerability_scan",
        "registry_credential_compromise",
        "future_github_pr_manipulation",
    ):
        assert required in scenarios


def test_linked_to_prior_baseline_blockers() -> None:
    linked = _model()["linkedBaselineBlockers"]
    assert {"step_54_1", "step_54_2", "step_54_3"} <= set(linked)
    assert linked["step_54_3"]
