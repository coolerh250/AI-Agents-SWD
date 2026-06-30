"""Step 61 -- backup target inventory."""

from __future__ import annotations

from shared.sdk.backup_restore_dr import load_targets, production_restore_allowed_count


def test_no_production_restore_target() -> None:
    assert production_restore_allowed_count() == 0
    for t in load_targets():
        assert t["restore_allowed_production"] is False


def test_no_secret_or_customer_data_backed_up() -> None:
    for t in load_targets():
        if t.get("contains_secret"):
            assert t.get("backup_allowed") is False
        assert t.get("contains_customer_data") is False


def test_required_fields_present() -> None:
    required = {
        "name",
        "source",
        "classification",
        "contains_secret",
        "backup_allowed",
        "restore_allowed_nonprod",
        "restore_allowed_production",
        "retention_class",
        "cleanup_allowed",
    }
    targets = load_targets()
    assert targets
    for t in targets:
        assert required <= set(t.keys())
