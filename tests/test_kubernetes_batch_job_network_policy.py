"""Step 51.2C2 -- batch job NetworkPolicy compatibility (DB-only egress)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NETPOL = (
    ROOT
    / "infra"
    / "kubernetes"
    / "charts"
    / "ai-agents-platform"
    / "templates"
    / "networkpolicies.yaml"
)


def _t() -> str:
    return NETPOL.read_text(encoding="utf-8")


def test_batch_egress_to_postgres_only() -> None:
    t = _t()
    assert "egress-batch-" in t
    assert "app.kubernetes.io/name: postgres" in t
    assert "port: 5432" in t


def test_postgres_ingress_from_batch() -> None:
    assert "ingress-postgres-batch" in _t()


def test_batch_selector_specific_not_broad() -> None:
    t = _t()
    # batch policies select on the specific batch-job label, not a broad component
    assert "ai-agents-swd/batch-job: {{ $job }}" in t


def test_batch_netpol_gated_dev_test_and_postgres() -> None:
    t = _t()
    assert "$pg.enabled" in t
    assert 'has $root.Values.global.environment (list "dev" "test")' in t


def test_no_external_egress_for_batch() -> None:
    t = _t()
    # the batch block adds only postgres egress + DNS is shared; no 0.0.0.0/0
    assert "0.0.0.0/0" not in t
