"""Step 51.2C1 -- storage consumer inventory completeness."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "infra" / "kubernetes" / "storage-consumer-inventory.yaml"

REQUIRED_FIELDS = {
    "component",
    "dataCategory",
    "path",
    "ownership",
    "writers",
    "readers",
    "lifecycle",
    "durability",
    "rebuildable",
    "confidentiality",
    "integrityRequirement",
    "currentStorage",
    "targetStrategy",
    "evidence",
}
STRATEGIES = {
    "ephemeralEmptyDir",
    "generatedPVC",
    "existingClaim",
    "externalService",
    "externalObjectStorePlaceholder",
    "imageContained",
    "unresolved",
}


def _inv() -> dict:
    return yaml.safe_load(INV.read_text(encoding="utf-8"))


def test_every_consumer_has_required_fields() -> None:
    for c in _inv()["consumers"]:
        missing = REQUIRED_FIELDS - set(c)
        assert not missing, f"{c.get('component')} missing {missing}"
        assert c["writers"], c["component"]
        assert c["evidence"], c["component"]


def test_target_strategies_valid() -> None:
    for c in _inv()["consumers"]:
        assert c["targetStrategy"] in STRATEGIES, c["targetStrategy"]


def test_required_categories_present() -> None:
    cats = {c["dataCategory"] for c in _inv()["consumers"]}
    for required in (
        "database",
        "redis",
        "workspace",
        "reports",
        "audit_evidence",
        "delivery_artifacts",
        "static_asset",
        "backup",
    ):
        assert required in cats, required


def test_postgres_is_only_named_compose_volume() -> None:
    consumers = {c["component"]: c for c in _inv()["consumers"]}
    pg = consumers["postgres"]
    assert pg["path"] == "/var/lib/postgresql/data"
    assert "postgres-data" in pg["currentStorage"]


def test_backup_consumer_deferred() -> None:
    backup = next(c for c in _inv()["consumers"] if c["dataCategory"] == "backup")
    assert backup["deferredTo"] == "51.2C2"
    assert backup["targetStrategy"] == "unresolved"
