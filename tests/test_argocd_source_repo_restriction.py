"""Step 51.3 -- source repo restriction (no wildcard, no credential URL)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ARGOCD = ROOT / "infra" / "gitops" / "argocd"
REPO = "https://github.com/coolerh250/AI-Agents-SWD.git"


def _docs() -> list[dict]:
    out = []
    for p in ARGOCD.rglob("*.yaml"):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            out.append(d)
    return out


def test_project_source_repos_exact() -> None:
    proj = next(d for d in _docs() if d.get("kind") == "AppProject")
    assert proj["spec"]["sourceRepos"] == [REPO]
    assert "*" not in proj["spec"]["sourceRepos"]


def test_application_repo_urls_exact() -> None:
    for d in _docs():
        if d.get("kind") == "Application":
            assert d["spec"]["source"]["repoURL"] == REPO, d["metadata"]["name"]


def test_no_credential_or_token_in_repo_url() -> None:
    for p in ARGOCD.rglob("*.yaml"):
        raw = p.read_text(encoding="utf-8")
        assert "@github.com" not in raw, p.name  # no user:token@host
        assert "git@" not in raw, p.name  # no SSH URL
