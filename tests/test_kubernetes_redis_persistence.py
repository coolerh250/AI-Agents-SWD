"""Step 51.2C1 -- Redis persistence baseline."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"


def _v(name: str = "values.yaml") -> dict:
    return yaml.safe_load((CHART / name).read_text(encoding="utf-8"))


def test_base_redis_generated_pvc_rwo_data() -> None:
    r = _v()["storage"]["redis"]
    assert r["strategy"] == "generatedPVC"
    assert r["persistenceEnabled"] is True
    assert r["accessMode"] == "ReadWriteOnce"
    assert r["mountPath"] == "/data"


def test_redis_no_real_class_or_claim() -> None:
    r = _v()["storage"]["redis"]
    assert r["storageClassName"] == ""
    assert r["existingClaim"] == ""


def test_staging_prod_redis_external_service() -> None:
    for f in ("values-staging-placeholder.yaml", "values-prod-placeholder.yaml"):
        r = _v(f)["storage"]["redis"]
        assert r["strategy"] == "externalService"
        assert r["persistenceEnabled"] is False


def test_redis_readonly_root_retained() -> None:
    # storage layer owns /data; 51.2A read-only root must stay true for redis
    assert _v()["components"]["redis"]["security"]["readOnlyRootFilesystem"] is True


def test_redis_internal_only_dev_test() -> None:
    assert _v()["components"]["redis"]["enabled"] is False
    assert _v("values-dev.yaml")["components"]["redis"]["enabled"] is True
    assert _v("values-test.yaml")["components"]["redis"]["enabled"] is True
