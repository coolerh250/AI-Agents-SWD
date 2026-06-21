"""Step 51.3 -- production is never activated (inactive + values fail-closed)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITOPS = ROOT / "infra" / "gitops"
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _merged_prod() -> dict:
    base = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    over = yaml.safe_load((CHART / "values-prod-placeholder.yaml").read_text(encoding="utf-8"))

    def merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in (b or {}).items():
            out[k] = merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return out

    return merge(base, over)


def test_production_env_inactive() -> None:
    envs = yaml.safe_load((GITOPS / "gitops-environments.yaml").read_text(encoding="utf-8"))[
        "environments"
    ]
    assert envs["production-placeholder"]["active"] is False
    assert envs["production-placeholder"]["disabled"] is True


def test_production_values_fail_closed() -> None:
    pv = _merged_prod()
    assert pv["global"]["realDeployEnabled"] is False
    assert pv["global"]["production"] is True
    assert pv["components"]["postgres"]["enabled"] is False
    assert pv["components"]["redis"]["enabled"] is False
    assert pv["batchJobs"]["migration"]["renderTemplate"] is False
    assert pv["batchJobs"]["backup"]["renderTemplate"] is False
    assert pv["batchJobs"]["restore"]["renderTemplate"] is False
    assert pv["networkPolicy"]["externalEgress"]["enabled"] is False


def test_app_of_apps_has_no_production() -> None:
    aoa = yaml.safe_load(
        (GITOPS / "argocd" / "app-of-apps" / "non-production.yaml").read_text(encoding="utf-8")
    )
    assert "production" not in aoa["spec"]["source"]["directory"]["include"]
