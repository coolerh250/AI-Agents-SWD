"""Step 51.2B -- staging/production network baseline is fail-closed."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

ENV_FILES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "production": "values-prod-placeholder.yaml",
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        out[k] = (
            _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
        )
    return out


def _merged(env: str) -> dict:
    base = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    return _deep_merge(base, yaml.safe_load((CHART / ENV_FILES[env]).read_text(encoding="utf-8")))


@pytest.mark.parametrize("env", list(ENV_FILES))
def test_default_deny_enabled_every_env(env: str) -> None:
    np = _merged(env)["networkPolicy"]
    assert np["enabled"] is True
    assert np["defaultDenyIngress"] is True
    assert np["defaultDenyEgress"] is True
    assert np["dns"]["enabled"] is True


@pytest.mark.parametrize("env", ["staging", "production"])
def test_staging_prod_no_external_or_ingress_controller(env: str) -> None:
    np = _merged(env)["networkPolicy"]
    assert np["externalEgress"]["enabled"] is False
    assert np["ingressController"]["enabled"] is False
    eds = _merged(env)["externalDataServices"]
    assert eds["postgres"]["enabled"] is False
    assert eds["redis"]["enabled"] is False


def test_validate_values_blocks_disabling_network_policy() -> None:
    v = (CHART / "templates" / "validate-values.yaml").read_text(encoding="utf-8")
    assert "networkPolicy.enabled must be true" in v
    assert "networkPolicy.externalEgress must be disabled" in v
    assert "production must not enable the external" in v
