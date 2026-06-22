"""Step 53 -- runtime secret references (disabled, unconfigured)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "runtime-secret-references.yaml"


def _refs() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["references"]


def test_required_refs_present() -> None:
    refs = _refs()
    for k in (
        "database_credential",
        "redis_credential",
        "audit_hmac_keyring",
        "llm_api_key",
        "notification_webhook",
    ):
        assert k in refs


def test_all_disabled_unconfigured_not_ready() -> None:
    for k, r in _refs().items():
        assert r["store"] == "disabled", k
        assert r["configured"] is False, k
        assert r["productionReady"] is False, k
        assert r["name"] == "" and r["key"] == "", k
