"""Step 54.4 -- release risk scoring policy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"


def _scoring() -> dict:
    data = (
        yaml.safe_load((SEC / "release-risk-scoring-policy.yaml").read_text(encoding="utf-8")) or {}
    )
    return data["riskScoring"]


def test_modeled_not_enforced_gate_disabled() -> None:
    s = _scoring()
    assert s["status"] == "modeled_not_enforced"
    assert s["productionReady"] is False
    assert s["productionGateEnabled"] is False


def test_blockers_define_critical_and_not_ready() -> None:
    blockers = _scoring()["blockers"]
    assert blockers["confirmedSecretLeak"] == "critical_blocker"
    assert blockers["criticalFinding"] == "critical_blocker"
    assert blockers["missingThreatModel"] == "not_ready"
    assert blockers["runtimeNotValidated"] == "not_ready"


def test_severity_weights_and_interpretation() -> None:
    s = _scoring()
    w = s["severityWeights"]
    assert w["critical"] >= w["high"] >= w["medium"] >= w["low"]
    interp = s["interpretation"]
    assert interp["scoreIsNotApproval"] is True
    assert interp["lowScoreIsNotProductionReady"] is True
    assert interp["missingRequiredEvidenceForcesNotReady"] is True
    assert interp["productionGateRemainsDisabled"] is True
