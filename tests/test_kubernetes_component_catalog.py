"""Step 51.1 -- component catalog completeness + classification."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "infra" / "kubernetes" / "runtime-inventory.yaml"
CATALOG = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "component-catalog.yaml"


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_all_deployment_targets_in_catalog() -> None:
    inv = _load(INVENTORY)
    catalog = _load(CATALOG)
    targets = {s["name"] for s in inv["services"] if s.get("kubernetesTarget") == "deployment"}
    assert targets, "no deployment targets found in inventory"
    assert targets <= set(catalog["components"]), targets - set(catalog["components"])


def test_one_shot_jobs_excluded_from_catalog() -> None:
    inv = _load(INVENTORY)
    catalog = _load(CATALOG)
    oneshot = {j["name"] for j in inv.get("oneShotJobs", [])}
    assert not (oneshot & set(catalog["components"])), oneshot & set(catalog["components"])


def test_catalog_components_have_required_fields() -> None:
    catalog = _load(CATALOG)
    for name, comp in catalog["components"].items():
        assert "enabled" in comp, name
        assert comp.get("type"), name
        assert comp["image"]["repository"], name
        assert comp["image"].get("tag"), name
        assert comp["image"].get("digest", "") == "", f"{name} must not pin a fake digest"
        assert comp["containerPort"], name
        assert comp["resources"]["requests"], name
        assert comp["resources"]["limits"], name


def test_catalog_ports_match_inventory() -> None:
    inv = {s["name"]: s for s in _load(INVENTORY)["services"]}
    catalog = _load(CATALOG)
    for name, comp in catalog["components"].items():
        assert comp["containerPort"] == inv[name]["port"], name


def test_vault_is_test_only_in_catalog() -> None:
    catalog = _load(CATALOG)
    assert catalog["components"]["vault"]["testOnly"] is True
    assert catalog["components"]["vault"]["enabled"] is False


def test_infrastructure_disabled_by_default() -> None:
    catalog = _load(CATALOG)
    for name in ("postgres", "redis", "vault"):
        assert catalog["components"][name]["enabled"] is False, name


def test_no_latest_tag_in_catalog() -> None:
    catalog = _load(CATALOG)
    for name, comp in catalog["components"].items():
        assert str(comp["image"]["tag"]) != "latest", name


def test_observability_deferred_not_workload() -> None:
    catalog = _load(CATALOG)
    deferred = catalog["deferred"]["observability"]["services"]
    assert set(deferred) == {"tempo", "prometheus", "alertmanager", "grafana"}
    for svc in deferred:
        assert svc not in catalog["components"], svc
