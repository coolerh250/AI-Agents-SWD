"""Step 53 -- disabled production secret store config."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "production-secret-store-disabled-config.yaml"


def _s() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["productionSecretStore"]


def test_disabled_fail_closed() -> None:
    s = _s()
    assert s["enabled"] is False
    assert s["configured"] is False
    assert s["provider"] == "disabled"
    assert s["failClosed"] is True
    assert s["productionReady"] is False


def test_no_value_access_no_rotation() -> None:
    s = _s()
    assert s["readSecretValuesEnabled"] is False
    assert s["writeSecretValuesEnabled"] is False
    assert s["rotationEnabled"] is False


def test_required_before_and_status() -> None:
    s = _s()
    for req in ("production_oidc", "production_backup", "production_deployment"):
        assert req in s["requiredBefore"]
    assert s["status"]["ready"] is False
