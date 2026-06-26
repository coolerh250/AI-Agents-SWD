"""Step 55.1 -- non-production cluster safety verifier (static guarantees)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_nonproduction_cluster_safety.py"


def _src() -> str:
    return VERIFIER.read_text(encoding="utf-8")


def test_verifier_exists_with_marker() -> None:
    assert VERIFIER.is_file()
    assert 'MARKER = "NONPROD_CLUSTER_SAFETY_VERIFY"' in _src()


def test_refuses_public_exposure_and_production_namespace() -> None:
    src = _src()
    assert "LoadBalancer" in src
    assert "NodePort" in src
    assert "ingress" in src.lower()
    # Production-substring namespace is rejected.
    assert 'if "prod" in NS.lower()' in src


def test_asserts_production_invariants_false() -> None:
    src = _src()
    assert "productionExecuted" in src
    assert "kubernetesProductionDeployPerformed" in src
    assert "argocdSyncPerformed" in src


def test_blocks_without_safe_cluster() -> None:
    # No safe cluster -> BLOCKED (never a faked PASS).
    src = _src()
    assert "detect_cluster()" in src
    assert "{MARKER}: BLOCKED" in src
