"""Step 52.3 -- break-glass model: defined, disabled."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "break-glass-model.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_disabled_no_route_no_button() -> None:
    bg = _d()["breakGlass"]
    assert bg["enabled"] is False
    assert bg["loginRouteExists"] is False
    assert bg["adminButtonExists"] is False
    assert bg["platformAdminAutomaticAccess"] is False


def test_requirements() -> None:
    req = _d()["breakGlass"]["requirements"]
    for k in (
        "productionIdentityRequired",
        "separateApprovalRequired",
        "timeBoundSessionRequired",
        "reasonRequired",
        "auditRequired",
        "postIncidentReviewRequired",
    ):
        assert req[k] is True


def test_prohibitions() -> None:
    pro = _d()["breakGlass"]["prohibitions"]
    for k in (
        "canBeTestLocal",
        "canBypassAudit",
        "autoGrantsKubernetes",
        "autoGrantsArgoCD",
        "autoGrantsGitHub",
        "autoGrantsProductionDeploy",
    ):
        assert pro[k] is False


def test_depends_on_production_approval_model() -> None:
    assert _d()["dependencies"]["productionApprovalModel"] == "60"
    assert _d()["status"]["productionReady"] is False
