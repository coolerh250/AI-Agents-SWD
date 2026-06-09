"""Stage 36 -- encryption key source + status (no key value carried)."""

from __future__ import annotations

from shared.sdk.backup import encryption_status, resolve_encryption_key_source


def test_env_key_source_marks_production_ready():
    cfg = resolve_encryption_key_source({"BACKUP_ENCRYPTION_KEY": "supersecret"})
    assert cfg.enabled is True
    assert cfg.mode == "openssl-aes-256-cbc"
    assert cfg.key_source == "env"
    assert cfg.production_ready is True
    # The key value MUST NOT leak through key_id; it's a sha256 prefix.
    assert cfg.key_id is not None
    assert cfg.key_id != "supersecret"
    assert len(cfg.key_id) == 8


def test_test_only_key_source_is_not_production_ready():
    cfg = resolve_encryption_key_source({"BACKUP_KEY_SOURCE": "test-only-generated"})
    assert cfg.enabled is True
    assert cfg.key_source == "test-only-generated"
    assert cfg.production_ready is False
    assert cfg.key_id == "test-only-ephemeral"


def test_missing_key_source_disables_encryption():
    cfg = resolve_encryption_key_source({})
    assert cfg.enabled is False
    assert cfg.mode == "none"
    assert cfg.key_source == "missing"
    assert cfg.production_ready is False


def test_encryption_status_dict_contains_no_secret():
    status = encryption_status({"BACKUP_ENCRYPTION_KEY": "abc123"})
    for forbidden in ("key", "secret", "token", "password"):
        for k, v in status.items():
            assert forbidden != k.lower() or v is None or "_id" in k or "_source" in k


def test_encryption_status_marks_test_only_not_production_ready():
    status = encryption_status({"BACKUP_KEY_SOURCE": "test-only-generated"})
    assert status["enabled"] is True
    assert status["production_ready"] is False


def test_encryption_status_marks_env_key_production_ready():
    status = encryption_status({"BACKUP_ENCRYPTION_KEY": "supersecret"})
    assert status["enabled"] is True
    assert status["production_ready"] is True
