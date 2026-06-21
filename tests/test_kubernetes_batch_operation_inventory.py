"""Step 51.2C2 -- batch operation inventory completeness + risk."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "infra" / "kubernetes" / "batch-operation-inventory.yaml"

EXPECTED_RISK = {
    "migration": "high",
    "encrypted-backup": "medium",
    "isolated-restore-drill": "critical",
}


def _ops() -> dict:
    inv = yaml.safe_load(INV.read_text(encoding="utf-8"))
    return {o["key"]: o for o in inv["operations"]}


def test_all_operations_present() -> None:
    ops = _ops()
    for k in EXPECTED_RISK:
        assert k in ops, k


def test_risk_classification() -> None:
    for k, o in _ops().items():
        assert o["risk"] == EXPECTED_RISK[k], k


def test_production_not_allowed() -> None:
    for k, o in _ops().items():
        assert o["productionAllowed"] is False, k


def test_lock_idempotency_timeout_explicit() -> None:
    for k, o in _ops().items():
        for f in ("lockRequired", "idempotent", "timeoutSeconds", "retryPolicy", "evidence"):
            assert f in o, f"{k} missing {f}"


def test_unresolved_marked_requires_cluster_smoke() -> None:
    for k, o in _ops().items():
        if o.get("unresolved"):
            assert o.get("runtimeCompatibility") == "requires_cluster_smoke", k
