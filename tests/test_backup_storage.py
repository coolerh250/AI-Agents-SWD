"""Stage 36 -- pluggable backup storage facade."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.backup import BackupStorage, storage_status
from shared.sdk.backup.models import STORAGE_MODE_DISABLED


def test_storage_status_defaults_to_local_filesystem():
    status = storage_status({})
    assert status["mode"] == "local-filesystem"
    assert status["production_ready"] is False


def test_storage_status_marks_s3_production_ready_with_credentials():
    status = storage_status(
        {
            "BACKUP_STORAGE_MODE": "s3-compatible-placeholder",
            "BACKUP_STORAGE_BUCKET": "my-bucket",
            "BACKUP_STORAGE_ACCESS_KEY_ID": "AKIA",
            "BACKUP_STORAGE_SECRET_ACCESS_KEY": "SECRET",
        }
    )
    assert status["mode"] == "s3-compatible-placeholder"
    assert status["bucket_configured"] is True
    assert status["access_key_configured"] is True
    assert status["secret_key_configured"] is True
    assert status["production_ready"] is True


def test_storage_status_disabled_mode():
    status = storage_status({"BACKUP_STORAGE_MODE": "disabled"})
    assert status["mode"] == "disabled"
    assert status["production_ready"] is False


def test_local_upload_and_download_roundtrip(tmp_path: Path):
    bucket = tmp_path / "bucket"
    src = tmp_path / "src.dump"
    src.write_bytes(b"backup-bytes")
    storage = BackupStorage(
        {
            "BACKUP_STORAGE_MODE": "local-filesystem",
            "BACKUP_STORAGE_BUCKET": str(bucket),
            "BACKUP_STORAGE_PREFIX": "bkp-x",
        }
    )
    up = storage.upload(src, "bkp-x")
    assert up.uploaded is True
    assert up.skipped is False
    assert up.bytes_transferred > 0
    assert up.uri is not None
    assert Path(up.uri).exists()

    target = tmp_path / "downloaded.dump"
    down = storage.download(up.uri, target)
    assert down.uploaded is True
    assert target.read_bytes() == b"backup-bytes"


def test_local_upload_missing_bucket_skips():
    storage = BackupStorage({"BACKUP_STORAGE_MODE": "local-filesystem"})
    decision = storage.upload(Path("/nonexistent/source.dump"), "bkp-x")
    assert decision.uploaded is False
    assert decision.skipped is True


def test_s3_mode_without_credentials_skips(tmp_path: Path):
    src = tmp_path / "x.dump"
    src.write_bytes(b"x")
    storage = BackupStorage({"BACKUP_STORAGE_MODE": "s3-compatible-placeholder"})
    decision = storage.upload(src, "bkp-x")
    assert decision.uploaded is False
    assert decision.skipped is True
    assert decision.reason == "credential_missing"


def test_s3_mode_with_credentials_skips_with_not_implemented(tmp_path: Path):
    src = tmp_path / "x.dump"
    src.write_bytes(b"x")
    storage = BackupStorage(
        {
            "BACKUP_STORAGE_MODE": "s3-compatible-placeholder",
            "BACKUP_STORAGE_BUCKET": "b",
            "BACKUP_STORAGE_ACCESS_KEY_ID": "A",
            "BACKUP_STORAGE_SECRET_ACCESS_KEY": "S",
        }
    )
    decision = storage.upload(src, "bkp-x")
    assert decision.uploaded is False
    assert decision.skipped is True
    assert decision.reason == "s3_upload_not_implemented"


def test_disabled_mode_skips(tmp_path: Path):
    src = tmp_path / "x.dump"
    src.write_bytes(b"x")
    storage = BackupStorage({"BACKUP_STORAGE_MODE": STORAGE_MODE_DISABLED})
    decision = storage.upload(src, "bkp-x")
    assert decision.skipped is True
    assert decision.reason == "storage_mode_disabled"
