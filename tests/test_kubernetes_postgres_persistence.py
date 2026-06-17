"""Step 51.2C1 -- PostgreSQL persistence baseline."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

BAD_SC = {"gp2", "gp3", "standard", "managed-premium", "ebs-sc", "do-block-storage", "local-path"}


def _v(name: str = "values.yaml") -> dict:
    return yaml.safe_load((CHART / name).read_text(encoding="utf-8"))


def test_base_postgres_generated_pvc_rwo() -> None:
    pg = _v()["storage"]["postgres"]
    assert pg["strategy"] == "generatedPVC"
    assert pg["persistenceEnabled"] is True
    assert pg["accessMode"] == "ReadWriteOnce"
    assert pg["mountPath"] == "/var/lib/postgresql/data"
    assert pg["size"].endswith(("Gi", "Mi", "Ti"))


def test_postgres_no_real_storage_class_or_claim() -> None:
    pg = _v()["storage"]["postgres"]
    assert pg["storageClassName"] == ""
    assert pg["existingClaim"] == ""
    assert pg["storageClassName"].lower() not in BAD_SC


def test_staging_prod_postgres_external_service() -> None:
    for f in ("values-staging-placeholder.yaml", "values-prod-placeholder.yaml"):
        pg = _v(f)["storage"]["postgres"]
        assert pg["strategy"] == "externalService"
        assert pg["persistenceEnabled"] is False


def test_postgres_internal_only_dev_test() -> None:
    # component disabled in base; only dev/test enable it
    assert _v()["components"]["postgres"]["enabled"] is False
    assert _v("values-dev.yaml")["components"]["postgres"]["enabled"] is True
    assert _v("values-test.yaml")["components"]["postgres"]["enabled"] is True
    for f in ("values-staging-placeholder.yaml", "values-prod-placeholder.yaml"):
        assert _v(f)["components"]["postgres"]["enabled"] is False
