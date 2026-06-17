"""Step 51.2C1 -- storage ownership catalog structure."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "infra" / "kubernetes" / "storage-ownership-catalog.yaml"

ENVS = {"dev", "test", "staging", "production"}


def _cat() -> dict:
    return yaml.safe_load(CAT.read_text(encoding="utf-8"))


def test_every_store_classified() -> None:
    for name, s in _cat()["stores"].items():
        for f in (
            "owner",
            "writers",
            "readers",
            "dataCategory",
            "lifecycle",
            "durability",
            "confidentiality",
            "integrityRequirement",
            "strategyByEnvironment",
            "productionConfigured",
        ):
            assert f in s, f"{name} missing {f}"
        assert set(s["strategyByEnvironment"]) == ENVS, name


def test_owners_and_writers_present() -> None:
    for name, s in _cat()["stores"].items():
        assert s["owner"], name
        assert s["writers"], name
        assert isinstance(s["readers"], list), name


def test_generated_pvc_stores_declared() -> None:
    cat = _cat()
    assert cat["generatedPvcStores"] == ["postgres-data", "redis-data"]
    for n in cat["generatedPvcStores"]:
        sbe = cat["stores"][n]["strategyByEnvironment"]
        assert sbe["dev"] == sbe["test"] == "generatedPVC"
        assert sbe["staging"] == sbe["production"] == "externalService"


def test_no_duplicate_store_ownership() -> None:
    stores = _cat()["stores"]
    pairs = [(s["owner"], s.get("mountPath", name)) for name, s in stores.items()]
    assert len(pairs) == len(set(pairs))


def test_backup_deferred_and_separate() -> None:
    backup = _cat()["deferred"]["backup-artifacts"]
    assert backup["deferredTo"] == "51.2C2"
    assert backup["separateFromActiveWorkspace"] is True
