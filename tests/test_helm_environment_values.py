"""Step 51.1 -- four environment values files parse + carry correct flags."""

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

EXPECTED_ENVIRONMENT = {
    "dev": "dev",
    "test": "test",
    "staging": "staging",
    "production": "production",
}


def _load(name: str) -> dict:
    with (CHART / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.mark.parametrize("env,fname", ENV_FILES.items())
def test_env_files_parse(env: str, fname: str) -> None:
    data = _load(fname)
    assert data["global"]["environment"] == EXPECTED_ENVIRONMENT[env]


@pytest.mark.parametrize("env,fname", ENV_FILES.items())
def test_real_deploy_disabled_everywhere(env: str, fname: str) -> None:
    assert _load(fname)["global"]["realDeployEnabled"] is False


def test_dev_and_test_enable_internal_infra() -> None:
    for fname in ("values-dev.yaml", "values-test.yaml"):
        comps = _load(fname)["components"]
        assert comps["postgres"]["enabled"] is True
        assert comps["redis"]["enabled"] is True
        assert comps["vault"]["enabled"] is True


def test_staging_and_prod_disable_internal_infra() -> None:
    for fname in ("values-staging-placeholder.yaml", "values-prod-placeholder.yaml"):
        comps = _load(fname)["components"]
        assert comps["postgres"]["enabled"] is False
        assert comps["redis"]["enabled"] is False
        assert comps["vault"]["enabled"] is False


def test_production_flag_only_in_production() -> None:
    assert _load("values-prod-placeholder.yaml")["global"]["production"] is True
    for fname in ("values-dev.yaml", "values-test.yaml", "values-staging-placeholder.yaml"):
        assert _load(fname)["global"]["production"] is False
