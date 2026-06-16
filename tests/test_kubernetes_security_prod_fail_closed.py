"""Step 51.2A -- staging/production cannot disable workload security."""

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


def _load(name: str) -> dict:
    return yaml.safe_load((CHART / name).read_text(encoding="utf-8"))


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _merged(env: str) -> dict:
    return _deep_merge(_load("values.yaml"), _load(ENV_FILES[env]))


@pytest.mark.parametrize("env", list(ENV_FILES))
def test_workload_security_enabled_in_every_env(env: str) -> None:
    ws = _merged(env)["global"]["workloadSecurity"]
    assert ws["enabled"] is True
    assert ws["runAsNonRoot"] is True
    assert ws["runAsUser"] != 0
    assert ws["seccompProfile"]["type"] == "RuntimeDefault"
    assert ws["allowPrivilegeEscalation"] is False
    assert ws["privileged"] is False
    assert ws["dropCapabilities"] == ["ALL"]
    assert ws["automountServiceAccountToken"] is False


def test_staging_and_prod_keep_security_and_no_infra() -> None:
    for env in ("staging", "production"):
        m = _merged(env)
        assert m["global"]["workloadSecurity"]["enabled"] is True
        assert m["components"]["vault"]["enabled"] is False


def test_validate_values_blocks_disabling_security() -> None:
    v = (CHART / "templates" / "validate-values.yaml").read_text(encoding="utf-8")
    assert "must not disable workloadSecurity" in v


def test_validate_values_present_for_staging_and_production() -> None:
    v = (CHART / "templates" / "validate-values.yaml").read_text(encoding="utf-8")
    assert 'eq $env "production"' in v
    assert 'eq $env "staging"' in v
