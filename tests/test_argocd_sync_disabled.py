"""Step 51.3 -- no automated sync / prune / selfHeal / CreateNamespace anywhere."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ARGOCD = ROOT / "infra" / "gitops" / "argocd"


def _apps() -> list[dict]:
    out = []
    for p in ARGOCD.rglob("*.yaml"):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("kind") == "Application":
            out.append(d)
    return out


def test_no_automated_sync() -> None:
    for a in _apps():
        sp = a["spec"].get("syncPolicy", {}) or {}
        assert "automated" not in sp, a["metadata"]["name"]


def test_no_create_namespace() -> None:
    for a in _apps():
        for opt in (a["spec"].get("syncPolicy", {}) or {}).get("syncOptions", []) or []:
            assert "CreateNamespace=true" not in opt, a["metadata"]["name"]


def test_no_allow_empty() -> None:
    for a in _apps():
        raw = yaml.dump(a)
        assert "allowEmpty: true" not in raw, a["metadata"]["name"]


def test_no_hooks_or_finalizers() -> None:
    for p in ARGOCD.rglob("*.yaml"):
        raw = p.read_text(encoding="utf-8")
        assert "argocd.argoproj.io/hook" not in raw, p.name
        assert "helm.sh/hook" not in raw, p.name
        assert "finalizers:" not in raw, p.name
