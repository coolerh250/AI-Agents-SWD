"""Step 51.2A -- workload security inventory completeness."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "infra" / "kubernetes" / "workload-security-inventory.yaml"
CATALOG = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "component-catalog.yaml"

FIRST_PARTY_CLASS = {
    "core_application",
    "governance_service",
    "communication_service",
    "worker",
    "agent",
}


def _load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_all_components_have_security_inventory() -> None:
    inv = _load(INVENTORY)["components"]
    catalog = _load(CATALOG)["components"]
    assert set(catalog) <= set(inv), set(catalog) - set(inv)
    assert len(inv) == 23, len(inv)


def test_first_party_restricted_targets() -> None:
    inv = _load(INVENTORY)["components"]
    fp = [n for n, c in inv.items() if c.get("classification") in FIRST_PARTY_CLASS]
    assert len(fp) == 20, fp
    for n in fp:
        c = inv[n]
        assert c["targetRunAsNonRoot"] is True, n
        assert c["targetRunAsUser"] == 10001, n
        assert c["readOnlyRootFilesystemTarget"] is True, n
        assert c["kubernetesApiRequired"] is False, n
        assert c["serviceAccountTokenRequired"] is False, n


def test_infra_overrides_documented() -> None:
    inv = _load(INVENTORY)["components"]
    # postgres + vault carry documented securityExceptions; redis keeps read-only root
    assert inv["postgres"]["securityExceptions"], "postgres needs documented exception"
    assert inv["postgres"]["readOnlyRootFilesystemTarget"] is False
    assert inv["vault"]["securityExceptions"], "vault needs documented exception"
    assert inv["vault"]["testOnly"] is True
    assert inv["redis"]["readOnlyRootFilesystemTarget"] is True


def test_no_unresolved_writable_paths() -> None:
    inv = _load(INVENTORY)
    assert inv.get("unresolvedWritablePaths") == []


def test_every_component_writable_paths_have_evidence() -> None:
    inv = _load(INVENTORY)["components"]
    for n, c in inv.items():
        for w in c.get("writablePaths", []) or []:
            assert w.get("evidence"), f"{n} writable path missing evidence"
