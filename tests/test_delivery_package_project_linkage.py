"""Step 57 -- delivery-package project linkage invariants."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LINK = ROOT / "infra" / "delivery" / "delivery-package-project-linkage.yaml"


def _d() -> dict:
    return (yaml.safe_load(LINK.read_text(encoding="utf-8")) or {})["deliveryPackageProjectLinkage"]


def test_link_fields() -> None:
    fields = _d()["linkFields"]
    for f in (
        "project_id",
        "work_item_id",
        "dispatch_id",
        "delivery_package_id",
        "acceptance_status",
    ):
        assert f in fields


def test_safety_invariants() -> None:
    inv = _d()["invariants"]
    assert inv["deliveryPackageReadyIsNotProductionApproval"] is True
    assert inv["workItemCompletedIsNotHumanAcceptance"] is True
    assert inv["humanAcceptanceIsNotDeploymentApproval"] is True
    assert inv["projectCompletedIsNotProductionRelease"] is True
    assert inv["productionReady"] is False
