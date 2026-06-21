"""Step 51.3 -- catalog <-> Application <-> values mapping consistency."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITOPS = ROOT / "infra" / "gitops"
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _cat() -> dict:
    return yaml.safe_load((GITOPS / "gitops-environments.yaml").read_text(encoding="utf-8"))


def test_catalog_values_match_applications() -> None:
    for env, e in _cat()["environments"].items():
        app_rel = e.get("applicationFile")
        assert app_rel, env
        app = yaml.safe_load((GITOPS / app_rel).read_text(encoding="utf-8"))
        vfs = app["spec"]["source"]["helm"]["valueFiles"]
        assert vfs == [e["valuesFile"]], env


def test_all_values_files_exist() -> None:
    for env, e in _cat()["environments"].items():
        assert (CHART / e["valuesFile"]).is_file(), env


def test_dev_test_active_staging_prod_inactive() -> None:
    envs = _cat()["environments"]
    assert envs["dev"]["active"] and envs["test"]["active"]
    assert not envs["staging-placeholder"]["active"]
    assert not envs["production-placeholder"]["active"]


def test_production_disabled_and_prod_values() -> None:
    prod = _cat()["environments"]["production-placeholder"]
    assert prod["disabled"] is True
    assert prod["valuesFile"] == "values-prod-placeholder.yaml"
