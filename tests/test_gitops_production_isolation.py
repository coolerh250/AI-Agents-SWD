"""Step 51.3 -- production placeholder isolation annotations + exclusion."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITOPS = ROOT / "infra" / "gitops"
PROD = GITOPS / "argocd" / "applications" / "production-placeholder.yaml"
AOA = GITOPS / "argocd" / "app-of-apps" / "non-production.yaml"

REQUIRED = [
    "ai-agents-swd/disabled-placeholder",
    "ai-agents-swd/do-not-sync",
    "ai-agents-swd/production-placeholder",
    "ai-agents-swd/real-deploy-enabled",
    "ai-agents-swd/requires-operator-approval",
    "ai-agents-swd/requires-production-oidc",
    "ai-agents-swd/requires-secret-store",
    "ai-agents-swd/requires-image-digest",
    "ai-agents-swd/requires-backup-target",
    "ai-agents-swd/requires-runtime-smoke",
]


def _prod() -> dict:
    return yaml.safe_load(PROD.read_text(encoding="utf-8"))


def test_required_isolation_annotations() -> None:
    ann = _prod()["metadata"]["annotations"]
    for a in REQUIRED:
        assert a in ann, a
    assert ann["ai-agents-swd/real-deploy-enabled"] == "false"


def test_no_automated_sync() -> None:
    assert "automated" not in (_prod()["spec"].get("syncPolicy", {}) or {})


def test_placeholder_destination() -> None:
    dest = _prod()["spec"]["destination"]
    assert dest["server"].endswith(".invalid")
    assert "placeholder" in dest["namespace"]


def test_excluded_from_app_of_apps() -> None:
    inc = yaml.safe_load(AOA.read_text(encoding="utf-8"))["spec"]["source"]["directory"]["include"]
    assert "production" not in inc
