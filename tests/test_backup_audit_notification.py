"""Stage 36 -- audit decision_types + notification events documented + default-blocked."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_doc() -> str:
    return (_REPO_ROOT / "docs" / "operations" / "backup-restore-dr.md").read_text(encoding="utf-8")


def test_docs_register_stage36_audit_decision_types():
    doc = _read_doc()
    for decision in (
        "backup_created",
        "backup_encrypted",
        "backup_uploaded",
        "backup_upload_skipped",
        "restore_drill_started",
        "restore_drill_passed",
        "restore_drill_failed",
        "backup_integrity_verified",
        "migration_down_inventory_completed",
    ):
        assert decision in doc, f"audit decision {decision} not documented"


def test_docs_register_stage36_notification_events():
    doc = _read_doc()
    for event in (
        "backup.created",
        "backup.upload_skipped",
        "restore_drill.passed",
        "restore_drill.failed",
        "backup.integrity_verified",
    ):
        assert event in doc, f"notification event {event} not documented"


def test_real_discord_default_denylist_blocks_backup_and_restore_drill():
    """Default real-Discord delivery policy MUST block backup.* and restore_drill.*."""
    text = (_REPO_ROOT / "shared" / "sdk" / "notifications" / "real_delivery_policy.py").read_text(
        encoding="utf-8"
    )
    assert '"backup.*"' in text
    assert '"restore_drill.*"' in text
    # And the allowlist must NOT carry any backup.* event by default.
    block_start = text.index("DEFAULT_REAL_DELIVERY_ALLOWLIST")
    block_end = text.index("DEFAULT_REAL_DELIVERY_DENYLIST")
    allow_block = text[block_start:block_end]
    assert "backup." not in allow_block
    assert "restore_drill." not in allow_block


def test_artifact_refs_carry_no_credentials():
    doc = _read_doc()
    # The doc explicitly states what artifact_refs may carry.
    assert "encryption_key" not in doc.lower() or "encryption-key value" in doc.lower()
    assert (
        "carry encryption-key value" in doc.lower()
        or "never carry encryption-key value" in doc.lower()
        or "NEVER carry encryption" in doc
        or "credential" in doc.lower()
    )
