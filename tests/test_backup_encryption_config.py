"""Stage 51 -- backup encryption config resolution (no raw key)."""

from __future__ import annotations

from shared.sdk.backup_dr.encryption_config import (
    encryption_gap_closed,
    resolve_encryption_config,
    safe_status,
)


def test_missing_key_reports_gap(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("BACKUP_DR_TEST_KEY_FILE", raising=False)
    monkeypatch.setattr(
        "shared.sdk.backup_dr.encryption_config.DEFAULT_KEY_FILE_PATHS",
        (str(tmp_path / "nope"),),
    )
    cfg = resolve_encryption_config()
    assert cfg.status == "missing"
    assert cfg.key_id is None
    assert encryption_gap_closed(cfg) is False


def test_test_key_file_closes_gap(tmp_path, monkeypatch) -> None:
    keyf = tmp_path / "backup-test-key"
    keyf.write_text("super-secret-test-key-material", encoding="utf-8")
    monkeypatch.setenv("BACKUP_DR_TEST_KEY_FILE", str(keyf))
    cfg = resolve_encryption_config()
    assert cfg.status == "configured"
    assert cfg.key_source == "key_file"
    assert cfg.key_id and len(cfg.key_id) == 12
    assert encryption_gap_closed(cfg) is True


def test_safe_status_never_carries_raw_key(tmp_path, monkeypatch) -> None:
    secret = "RAW-KEY-VALUE-DO-NOT-LEAK"
    keyf = tmp_path / "backup-test-key"
    keyf.write_text(secret, encoding="utf-8")
    monkeypatch.setenv("BACKUP_DR_TEST_KEY_FILE", str(keyf))
    cfg = resolve_encryption_config()
    status = safe_status(cfg)
    assert secret not in str(status)
    assert status["raw_key_persisted"] is False
    # key_id is a hash prefix, not the key itself.
    assert status["key_id"] != secret


def test_key_id_is_content_hash(tmp_path, monkeypatch) -> None:
    keyf = tmp_path / "k"
    keyf.write_text("aaa", encoding="utf-8")
    monkeypatch.setenv("BACKUP_DR_TEST_KEY_FILE", str(keyf))
    id1 = resolve_encryption_config().key_id
    keyf.write_text("bbb", encoding="utf-8")
    id2 = resolve_encryption_config().key_id
    assert id1 != id2
