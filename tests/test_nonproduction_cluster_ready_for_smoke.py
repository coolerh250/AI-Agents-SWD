"""Step 55.1 -- combined cluster-ready-for-smoke verifier (static guarantees)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / "scripts" / "verify_nonproduction_cluster_ready_for_smoke.sh"
GENERATOR = ROOT / "scripts" / "run_nonproduction_runtime_smoke.py"


def _src() -> str:
    return COMBINED.read_text(encoding="utf-8")


def test_combined_exists_with_final_marker() -> None:
    assert COMBINED.is_file()
    src = _src()
    assert "NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY: PASS" in src
    assert "NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY: BLOCKED" in src
    assert "NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY: FAIL" in src


def test_chains_required_verifiers() -> None:
    src = _src()
    for v in (
        "verify_nonproduction_kubernetes_tooling.py",
        "verify_kind_nonproduction_cluster.py",
        "verify_nonproduction_cluster_bootstrap.py",
        "verify_nonproduction_cluster_safety.py",
        "verify_nonproduction_namespace_plan.py",
        "verify_nonproduction_kubernetes_runtime_smoke.sh",
    ):
        assert v in src


def test_confirms_no_production_execution() -> None:
    src = _src()
    assert "production_executed_true_count" in src
    assert "argocd_sync_performed" in src
    assert "True False False False 0" in src


def test_generator_is_read_only_no_deploy() -> None:
    src = GENERATOR.read_text(encoding="utf-8")
    assert 'MARKER = "NONPROD_RUNTIME_SMOKE_RUN"' in src
    assert '"productionExecuted": False' in src
    assert '"argocdSyncPerformed": False' in src
