"""Step 54.4 -- release risk summary model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"


def _model() -> dict:
    data = (
        yaml.safe_load((SEC / "release-risk-summary-model.yaml").read_text(encoding="utf-8")) or {}
    )
    return data["releaseRiskSummaryModel"]


def test_not_production_ready_or_gate() -> None:
    m = _model()
    assert m["productionReady"] is False
    assert m["productionGateIntegrated"] is False


def test_status_enum_excludes_production_ready() -> None:
    enum = set(_model()["statusEnum"])
    assert "production_ready" not in enum
    assert "production_approved" not in enum
    assert {"not_ready", "blocked"} <= enum


def test_forbidden_statuses_listed() -> None:
    forbidden = set(_model()["forbiddenStatuses"])
    assert {"production_ready", "production_approved"} <= forbidden


def test_inputs_and_no_approval() -> None:
    m = _model()
    assert m["inputs"]
    appr = m["approval"]
    assert appr["producesProductionApproval"] is False
    assert appr["producesDeploymentApproval"] is False
    assert appr["humanApprovalStillRequired"] is True
