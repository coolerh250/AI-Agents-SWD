"""Stage 51 -- migration rollback catalog completeness + classification."""

from __future__ import annotations

from shared.sdk.backup_dr.migration_catalog import (
    build_migration_catalog,
    catalog_summary,
    classify_migration,
    migration_down_gap_closed,
)


def test_real_migrations_catalog_complete() -> None:
    entries = build_migration_catalog("migrations")
    assert entries, "expected migrations to exist"
    summary = catalog_summary(entries)
    assert summary["unknown"] == 0
    assert summary["complete"] is True
    assert migration_down_gap_closed(entries) is True


def test_no_unknown_classification() -> None:
    entries = build_migration_catalog("migrations")
    assert all(e.reversibility != "unknown" for e in entries)


def test_forward_only_and_manual_have_notes() -> None:
    entries = build_migration_catalog("migrations")
    for e in entries:
        if e.reversibility in ("forward_only", "manual_rollback_required"):
            assert e.rollback_notes, f"{e.migration_file} missing rollback notes"


def test_additive_migration_is_forward_only(tmp_path) -> None:
    f = tmp_path / "099_additive.sql"
    f.write_text("CREATE TABLE IF NOT EXISTS foo (id int);", encoding="utf-8")
    e = classify_migration(f, has_down=False)
    assert e.reversibility == "forward_only"
    assert e.rollback_notes


def test_destructive_migration_manual_rollback(tmp_path) -> None:
    f = tmp_path / "100_drop.sql"
    f.write_text("DROP TABLE foo;", encoding="utf-8")
    e = classify_migration(f, has_down=False)
    assert e.reversibility == "manual_rollback_required"
    assert e.risk_level == "high"
    assert e.rollback_notes


def test_down_script_makes_reversible(tmp_path) -> None:
    f = tmp_path / "101_x.sql"
    f.write_text("DROP TABLE foo;", encoding="utf-8")
    e = classify_migration(f, has_down=True)
    assert e.reversibility == "reversible"
    assert e.down_script_available is True
