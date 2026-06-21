"""Step 51.2C2 -- migration locking + idempotency model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
WRAPPER = ROOT / "scripts" / "k8s_apply_migrations.py"


def _v() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_lock_required_advisory() -> None:
    lock = _v()["batchJobs"]["migration"]["lock"]
    assert lock["required"] is True
    assert lock["mode"] == "postgres_advisory_lock"


def test_wrapper_uses_pg_advisory_lock() -> None:
    src = WRAPPER.read_text(encoding="utf-8")
    assert "pg_advisory_lock(hashtext($1)::bigint)" in src
    assert "pg_advisory_unlock" in src


def test_wrapper_forward_only() -> None:
    src = WRAPPER.read_text(encoding="utf-8")
    # never applies *_down.sql
    assert "_down.sql" in src  # referenced only to EXCLUDE
    assert 'endswith("_down.sql")' in src


def test_wrapper_no_kubernetes_lease() -> None:
    src = WRAPPER.read_text(encoding="utf-8")
    # locking is a Postgres advisory lock, NOT a Kubernetes Lease API
    assert "coordination.k8s.io" not in src
    assert "pg_advisory_lock" in src


def test_wrapper_execution_gated() -> None:
    src = WRAPPER.read_text(encoding="utf-8")
    assert "AIAGENTS_BATCH_EXECUTE" in src
