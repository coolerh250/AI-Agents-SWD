"""Step 51.2C1 -- data lifecycle classification rules."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "infra" / "kubernetes" / "storage-ownership-catalog.yaml"


def _stores() -> dict:
    return yaml.safe_load(CAT.read_text(encoding="utf-8"))["stores"]


def test_infrastructure_state_not_ephemeral() -> None:
    for n, s in _stores().items():
        if s["lifecycle"] == "infrastructure_state":
            assert s["durability"] != "ephemeral", n


def test_database_not_fully_rebuildable() -> None:
    for n, s in _stores().items():
        if s["dataCategory"] == "database":
            assert s["rebuildable"] != "fully_rebuildable", n


def test_audit_stores_high_integrity() -> None:
    for n, s in _stores().items():
        if s["lifecycle"] == "audit_retained" or s["dataCategory"] == "audit_evidence":
            assert s["integrityRequirement"] in ("high", "audit_critical"), n


def test_workspace_honest_ephemeral() -> None:
    ws = _stores()["workspace-scratch"]
    assert ws["durability"] == "ephemeral"
    assert ws["persistenceSolved"] is False
    assert ws["lifecycleBoundary"]["durableAcrossRestart"] is False


def test_unresolved_stores_have_future_target_and_fail_closed() -> None:
    for n, s in _stores().items():
        if "unresolved" in set(s["strategyByEnvironment"].values()):
            assert s.get("futureTarget"), n
            assert s["productionConfigured"] is False, n


def test_no_fake_durability() -> None:
    for n, s in _stores().items():
        if s["durability"] == "ephemeral":
            assert s.get("persistenceSolved", False) is False, n
