"""Step 55.1 -- non-production Kubernetes tooling inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "infra" / "kubernetes" / "nonproduction-tooling-inventory.yaml"


def _inv() -> dict:
    return (yaml.safe_load(INVENTORY.read_text(encoding="utf-8")) or {})[
        "nonProductionToolingInventory"
    ]


def test_no_registry_login_or_image_push() -> None:
    inv = _inv()
    assert inv["registryLoginPerformed"] is False
    assert inv["imagePushPerformed"] is False


def test_required_tools_recorded_without_production_credential() -> None:
    tools = {t["name"]: t for t in _inv()["tools"]}
    for name in ("kubectl", "helm", "kind"):
        assert tools[name]["required"] is True
        assert tools[name]["productionCredentialRequired"] is False
        assert tools[name]["version"]


def test_argocd_and_registry_helpers_not_installed() -> None:
    not_installed = set(_inv().get("notInstalled", []))
    assert "argocd-cli" in not_installed
    assert "registry-credential-helper" in not_installed
