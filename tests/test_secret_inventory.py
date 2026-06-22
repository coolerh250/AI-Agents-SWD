"""Step 53 -- secret inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-inventory.yaml"
REQUIRED_CATEGORIES = {
    "identity",
    "session",
    "csrf",
    "database",
    "redis",
    "backup",
    "audit",
    "gitops",
    "kubernetes",
    "github",
    "registry",
    "llm",
    "notification",
    "storage",
    "break_glass",
}


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_all_categories_covered() -> None:
    cats = {s["category"] for s in _d()["secrets"]}
    assert REQUIRED_CATEGORIES <= cats


def test_no_value_in_repo() -> None:
    assert all(s["valueStoredInRepo"] is False for s in _d()["secrets"])


def test_production_secrets_unconfigured_store_required() -> None:
    for s in _d()["secrets"]:
        if s.get("productionRequired"):
            assert s["productionConfigured"] is False, s["key"]
            assert s["secretStoreRequired"] is True, s["key"]


def test_every_secret_has_owner_and_references() -> None:
    for s in _d()["secrets"]:
        assert s.get("owner")
        assert isinstance(s.get("references"), list)


def test_meta_no_real_values() -> None:
    m = _d()["meta"]
    assert m["noRealSecretValues"] is True
    assert m["productionSecretStoreConfigured"] is False
