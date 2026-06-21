"""Step 51.3 -- GitOps environment catalog structure."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "infra" / "gitops" / "gitops-environments.yaml"
REPO = "https://github.com/coolerh250/AI-Agents-SWD.git"


def _cat() -> dict:
    return yaml.safe_load(CAT.read_text(encoding="utf-8"))


def test_catalog_source() -> None:
    c = _cat()
    assert c["source"]["repoURL"] == REPO
    assert c["source"]["chartPath"] == "infra/kubernetes/charts/ai-agents-platform"
    assert c["project"] == "ai-agents-platform"


def test_all_environments_present() -> None:
    envs = _cat()["environments"]
    assert set(envs) == {"dev", "test", "staging-placeholder", "production-placeholder"}


def test_no_auto_sync_anywhere() -> None:
    for env, e in _cat()["environments"].items():
        assert e["automatedSync"] is False, env


def test_meta_not_connected() -> None:
    meta = _cat()["meta"]
    assert meta["clusterConnected"] is False
    assert meta["argocdInstalled"] is False
    assert meta["syncPerformed"] is False
