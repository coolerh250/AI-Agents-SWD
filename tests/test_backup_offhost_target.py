"""Stage 51 -- mock off-host target + readback verification, no real cloud."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.backup_dr.offhost_target import build_mock_offhost_target
from shared.sdk.backup_dr.offhost_transfer import offhost_gap_closed, transfer_to_offhost


def test_mock_target_no_cloud_write(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BACKUP_DR_OFFHOST_DIR", str(tmp_path / "offhost"))
    t = build_mock_offhost_target()
    assert t.target_type == "mock_local_remote"
    assert t.real_cloud_write_enabled is False


def test_cloud_target_recognized_but_disabled(monkeypatch) -> None:
    monkeypatch.setenv("BACKUP_DR_CLOUD_TARGET_TYPE", "s3")
    t = build_mock_offhost_target()
    assert t.target_type == "s3_disabled"
    assert t.status == "disabled"
    assert t.real_cloud_write_enabled is False


def test_transfer_readback_verified(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BACKUP_DR_OFFHOST_DIR", str(tmp_path / "offhost"))
    art = tmp_path / "backup.enc"
    art.write_bytes(b"ENCRYPTED-CONTENT")
    t = build_mock_offhost_target()
    tr = transfer_to_offhost(source_path=str(art), target=t)
    assert tr.status == "verified"
    assert tr.readback_verified is True
    assert tr.real_cloud_write_performed is False
    assert tr.source_checksum_sha256 == tr.target_checksum_sha256
    assert offhost_gap_closed(tr) is True
    assert Path(tr.target_path).is_file()


def test_transfer_missing_source_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BACKUP_DR_OFFHOST_DIR", str(tmp_path / "offhost"))
    t = build_mock_offhost_target()
    tr = transfer_to_offhost(source_path=str(tmp_path / "missing.enc"), target=t)
    assert tr.status == "failed"
    assert offhost_gap_closed(tr) is False
