"""Stage 36 -- BackupManifest dataclass + serialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.sdk.backup import (
    MANIFEST_SCHEMA_VERSION,
    BackupManifest,
    load_manifest,
    write_manifest,
)


def _make(**overrides):
    base = {
        "backup_id": "bkp-test-0001",
        "created_at": "2026-06-09T00:00:00Z",
        "environment": "local",
        "source_database": "aiagents",
        "source_host": "postgres",
        "pg_version": "16.2",
        "backup_format": "pg_dump-custom",
        "backup_file": "backups/aiagents-x.dump.enc",
        "backup_size_bytes": 12345,
        "checksum_sha256": "a" * 64,
        "encrypted": True,
        "encryption_mode": "openssl-aes-256-cbc",
        "encryption_key_id": "deadbeef",
        "compression": "pg_dump-custom-zlib",
        "off_host_uploaded": False,
        "off_host_uri": None,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "included_tables": ["audit_logs", "workflow_states"],
        "row_count_summary": {"audit_logs": 1000, "workflow_states": 50},
        "audit_chain_latest_hash": "f" * 64,
        "created_by": "scripts/backup_postgres_encrypted.sh",
        "production_executed": False,
    }
    base.update(overrides)
    return BackupManifest(**base)


def test_manifest_canonical_json_is_deterministic():
    m1 = _make()
    m2 = _make()
    assert m1.to_canonical_json() == m2.to_canonical_json()


def test_manifest_filename_matches_backup_id():
    m = _make(backup_id="bkp-99")
    assert m.manifest_filename() == "backup_manifest_bkp-99.json"


def test_manifest_production_executed_is_pinned_false():
    m = _make()
    # Even if a caller tries to flip the flag, __post_init__ overwrites
    # back to False -- Stage 36 forbids production backups via this path.
    m.production_executed = True
    m.__post_init__()
    assert m.production_executed is False


def test_manifest_rejects_forbidden_metadata_keys():
    with pytest.raises(ValueError):
        _make(row_count_summary={"encryption_key": 1})
    with pytest.raises(ValueError):
        _make(included_tables=["password"])


def test_manifest_requires_backup_id_and_checksum():
    with pytest.raises(ValueError):
        _make(backup_id="")
    with pytest.raises(ValueError):
        _make(checksum_sha256="")


def test_manifest_contains_no_secret_keys():
    m = _make()
    payload = m.to_canonical_json()
    parsed = json.loads(payload)
    for forbidden in (
        "encryption_key",
        "encryption_key_value",
        "db_password",
        "password",
        "storage_access_key",
        "storage_secret_access_key",
        "token",
        "secret",
    ):
        assert forbidden not in parsed
    # The opaque key_id label is allowed -- it's not the key value.
    assert parsed["encryption_key_id"] == "deadbeef"


def test_manifest_write_and_load_roundtrip(tmp_path: Path):
    m = _make()
    written = write_manifest(m, tmp_path)
    assert written.exists()
    loaded = load_manifest(written)
    assert loaded.backup_id == m.backup_id
    assert loaded.checksum_sha256 == m.checksum_sha256
    assert loaded.encrypted is True
    assert loaded.encryption_mode == "openssl-aes-256-cbc"
    assert loaded.production_executed is False
    assert loaded.row_count_summary == m.row_count_summary
