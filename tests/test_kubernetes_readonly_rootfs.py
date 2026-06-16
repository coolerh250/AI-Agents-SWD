"""Step 51.2A -- read-only root filesystem baseline + documented exceptions."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
INVENTORY = ROOT / "infra" / "kubernetes" / "workload-security-inventory.yaml"

FIRST_PARTY = {"application", "governance", "communication", "worker", "agent"}


def _values() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_global_default_read_only_root_true() -> None:
    assert _values()["global"]["workloadSecurity"]["readOnlyRootFilesystem"] is True


def test_first_party_do_not_disable_read_only_root() -> None:
    comps = _values()["components"]
    for n, c in comps.items():
        if c["type"] in FIRST_PARTY:
            sec = c.get("security", {}) or {}
            # first-party may omit (inherit true) but must never set false
            assert sec.get("readOnlyRootFilesystem", True) is True, n


def test_infra_exceptions_match_inventory() -> None:
    comps = _values()["components"]
    inv = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))["components"]
    assert comps["postgres"]["security"]["readOnlyRootFilesystem"] is False
    assert inv["postgres"]["readOnlyRootFilesystemTarget"] is False
    assert comps["redis"]["security"]["readOnlyRootFilesystem"] is True
    assert comps["vault"]["security"]["readOnlyRootFilesystem"] is False
    assert inv["vault"]["readOnlyRootFilesystemTarget"] is False
