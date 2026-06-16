"""Step 51.2B -- ingress-controller policy disabled (no empty selectors)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

ENV_FILES = [
    "values.yaml",
    "values-dev.yaml",
    "values-test.yaml",
    "values-staging-placeholder.yaml",
    "values-prod-placeholder.yaml",
]


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        out[k] = (
            _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
        )
    return out


def _merged(env_file: str) -> dict:
    base = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    if env_file == "values.yaml":
        return base
    return _deep_merge(base, yaml.safe_load((CHART / env_file).read_text(encoding="utf-8")))


def test_ingress_controller_disabled_in_every_env() -> None:
    for f in ENV_FILES:
        ic = _merged(f)["networkPolicy"]["ingressController"]
        assert ic["enabled"] is False, f


def test_validate_values_blocks_prod_ingress_controller() -> None:
    v = (CHART / "templates" / "validate-values.yaml").read_text(encoding="utf-8")
    assert "production must not enable the ingress-controller policy" in v
    assert "ingressController.namespaceSelector must not be empty when enabled" in v


def test_template_guards_ingress_controller() -> None:
    tpl = (CHART / "templates" / "networkpolicies.yaml").read_text(encoding="utf-8")
    assert "if $np.ingressController.enabled" in tpl
