"""Step 53 -- backup secret references (disabled, unconfigured)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "backup-secret-references.yaml"


def _refs() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["references"]


def test_required_refs_present() -> None:
    refs = _refs()
    for k in (
        "backup_encryption_key",
        "backup_target_credential",
        "restore_credential",
        "off_host_provider_credential",
    ):
        assert k in refs


def test_all_disabled_unconfigured_not_ready() -> None:
    for k, r in _refs().items():
        assert r["store"] == "disabled", k
        assert r["configured"] is False, k
        assert r["productionReady"] is False, k
        assert r["name"] == "" and r["key"] == "", k
