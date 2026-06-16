"""Step 51.1 -- production placeholder is fail-closed and non-deployable."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
PROD = CHART / "values-prod-placeholder.yaml"


def _prod() -> dict:
    with PROD.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_production_true_real_deploy_false() -> None:
    g = _prod()["global"]
    assert g["environment"] == "production"
    assert g["production"] is True
    assert g["realDeployEnabled"] is False


def test_auth_and_operator_actions_disabled() -> None:
    ac = _prod()["platform"]["adminConsole"]
    assert ac["testAuthEnabled"] is False
    assert ac["productionAuthEnabled"] is False
    assert ac["oidcEnabled"] is False
    assert ac["operatorActionsEnabled"] is False


def test_integrations_disabled() -> None:
    ig = _prod()["platform"]["integrations"]
    assert ig["githubWrite"] is False
    assert ig["prCreation"] is False
    assert ig["deployment"] is False
    assert ig["realLlm"] is False
    assert ig["externalDelivery"] is False
    assert ig["productionBackupSchedule"] is False


def test_internal_infra_disabled() -> None:
    comps = _prod()["components"]
    assert comps["postgres"]["enabled"] is False
    assert comps["redis"]["enabled"] is False
    assert comps["vault"]["enabled"] is False


def test_no_secret_creation_only_named_reference() -> None:
    secrets = _prod()["secrets"]
    assert secrets["create"] is False
    assert isinstance(secrets["existingSecret"], str) and secrets["existingSecret"]


def test_no_real_hostname_or_credential_in_prod_file() -> None:
    raw = PROD.read_text(encoding="utf-8")
    for pat in ("password:", "PRIVATE KEY", "ghp_", "https://", "http://"):
        assert pat not in raw, f"prod placeholder must not contain {pat!r}"
