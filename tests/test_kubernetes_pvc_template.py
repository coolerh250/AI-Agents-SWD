"""Step 51.2C1 -- PVC template gating + safety (template text level)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
PVC = CHART / "templates" / "persistentvolumeclaims.yaml"


def _t() -> str:
    return PVC.read_text(encoding="utf-8")


def test_template_exists() -> None:
    assert PVC.is_file()


def test_only_datastores_generate_pvc() -> None:
    t = _t()
    assert 'list "postgres" "redis"' in t


def test_pvc_gated_dev_test_generated_persistence_enabled() -> None:
    t = _t()
    assert 'eq $s.strategy "generatedPVC"' in t
    assert "$s.persistenceEnabled" in t
    assert "$comp.enabled" in t
    assert "has $env $devtest" in t


def test_pvc_deterministic_name() -> None:
    assert "{{ $fullname }}-{{ $key }}-data" in _t()


def test_pvc_has_no_unsafe_fields() -> None:
    t = _t()
    for forbidden in ("hostPath", "volumeName", "dataSource", "selector:", "nfs:", "csi:"):
        assert forbidden not in t, forbidden


def test_pvc_storage_class_only_when_non_empty() -> None:
    t = _t()
    assert "if $s.storageClassName" in t
