"""Step 53 -- secret audit model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-audit-model.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_events_present() -> None:
    keys = {e["key"] for e in _d()["events"]}
    for k in (
        "secret_ref_registered",
        "secret_rotation_requested",
        "secret_access_denied",
        "secret_store_unavailable",
        "secret_validation_failed",
    ):
        assert k in keys


def test_records_metadata_not_value() -> None:
    rf = _d()["recordedFields"]
    assert rf["actorRole"] is True
    assert rf["approvalReference"] is True
    assert rf["correlationId"] is True


def test_never_records_value() -> None:
    never = _d()["neverRecorded"]
    for k in ("secret_value", "raw_token", "private_key", "client_secret", "password", "jwt"):
        assert k in never
    assert _d()["productionMutation"] == "deferred"
