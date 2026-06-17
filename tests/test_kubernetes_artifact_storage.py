"""Step 51.2C1 -- reports / artifacts storage model + backup separation."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
CAT = ROOT / "infra" / "kubernetes" / "storage-ownership-catalog.yaml"


def _v(name: str = "values.yaml") -> dict:
    return yaml.safe_load((CHART / name).read_text(encoding="utf-8"))


def _cat() -> dict:
    return yaml.safe_load(CAT.read_text(encoding="utf-8"))


def test_artifacts_external_object_store_placeholder_disabled() -> None:
    a = _v()["storage"]["artifacts"]
    assert a["strategy"] == "externalObjectStorePlaceholder"
    assert a["persistenceEnabled"] is False
    assert a["existingClaim"] == ""
    assert a["productionConfigured"] is False


def test_admin_static_image_contained() -> None:
    stores = _cat()["stores"]
    # admin console static assets are NOT a store (image-contained)
    assert "admin-console-static" not in stores
    inv = yaml.safe_load(
        (ROOT / "infra" / "kubernetes" / "storage-consumer-inventory.yaml").read_text("utf-8")
    )
    admin = next(c for c in inv["consumers"] if c["dataCategory"] == "static_asset")
    assert admin["targetStrategy"] == "imageContained"


def test_delivery_evidence_separate_from_backup() -> None:
    cat = _cat()
    da = cat["stores"]["delivery-artifacts"]
    assert da["dataCategory"] == "delivery_artifacts"
    assert cat["deferred"]["backup-artifacts"]["separateFromActiveWorkspace"] is True


def test_audit_evidence_canonical_in_postgres() -> None:
    audit = _cat()["stores"]["audit-evidence-export"]
    assert audit["canonicalRecordsLocation"] == "postgresql"
    assert audit["integrityRequirement"] == "audit_critical"
