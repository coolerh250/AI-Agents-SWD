"""Step 51.3 -- ArgoCD Application manifests + values mapping."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "infra" / "gitops" / "argocd" / "applications"
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
REPO = "https://github.com/coolerh250/AI-Agents-SWD.git"
CHART_PATH = "infra/kubernetes/charts/ai-agents-platform"

EXPECTED = {
    "dev.yaml": ("ai-agents-platform-dev", "values-dev.yaml"),
    "test.yaml": ("ai-agents-platform-test", "values-test.yaml"),
    "staging-placeholder.yaml": (
        "ai-agents-platform-staging-placeholder",
        "values-staging-placeholder.yaml",
    ),
    "production-placeholder.yaml": (
        "ai-agents-platform-production-placeholder",
        "values-prod-placeholder.yaml",
    ),
}


def _a(name: str) -> dict:
    return yaml.safe_load((APPS / name).read_text(encoding="utf-8"))


def test_all_applications_valid() -> None:
    for fn, (name, vf) in EXPECTED.items():
        a = _a(fn)
        assert a["kind"] == "Application", fn
        assert a["metadata"]["name"] == name
        spec = a["spec"]
        assert spec["project"] == "ai-agents-platform"
        assert spec["source"]["repoURL"] == REPO
        assert spec["source"]["path"] == CHART_PATH
        assert spec["source"]["helm"]["valueFiles"] == [vf]


def test_values_files_exist() -> None:
    for _fn, (_name, vf) in EXPECTED.items():
        assert (CHART / vf).is_file(), vf


def test_target_revision_fixed() -> None:
    for fn in EXPECTED:
        rev = _a(fn)["spec"]["source"]["targetRevision"]
        assert rev not in (None, "", "HEAD", "*"), fn


def test_no_finalizers() -> None:
    for fn in EXPECTED:
        assert not _a(fn)["metadata"].get("finalizers"), fn
