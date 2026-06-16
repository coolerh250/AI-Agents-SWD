"""Stage 51 -- manifest builder carries key_id but never a raw key / password."""

from __future__ import annotations

from shared.sdk.backup_dr.backup_runner import build_backup_run
from shared.sdk.backup_dr.encryption_config import resolve_encryption_config
from shared.sdk.backup_dr.manifest_builder import build_manifest, manifest_contains_secret


def _enc(tmp_path, monkeypatch):
    keyf = tmp_path / "k"
    keyf.write_text("test-key", encoding="utf-8")
    monkeypatch.setenv("BACKUP_DR_TEST_KEY_FILE", str(keyf))
    return resolve_encryption_config()


def test_manifest_includes_key_id_not_raw_key(tmp_path, monkeypatch) -> None:
    enc = _enc(tmp_path, monkeypatch)
    run = build_backup_run(
        backup_key="b1",
        source_database="aiagents",
        encrypted=True,
        checksum_sha256="aa",
        encrypted_checksum_sha256="bb",
    )
    m = build_manifest(
        backup_run=run,
        encryption=enc,
        schema_migration_count=22,
        table_count=40,
        row_count_summary={"audit_logs": 5},
    )
    assert m.encryption_key_id == enc.key_id
    assert m.artifact_checksum_sha256 == "aa"
    assert "test-key" not in str(m.model_dump())
    assert manifest_contains_secret(m) is False


def test_manifest_secret_detector_flags_password() -> None:
    run = build_backup_run(backup_key="b", source_database="db", encrypted=True)
    m = build_manifest(backup_run=run, encryption=None)
    m.manifest_json["leak"] = "password=hunter2"
    assert manifest_contains_secret(m) is True
