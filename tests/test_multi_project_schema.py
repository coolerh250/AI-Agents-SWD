"""Step 57 -- multi-project schema (migration 024)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = (
    (ROOT / "migrations" / "024_multi_project_work_item_dispatch.sql")
    .read_text(encoding="utf-8")
    .lower()
)


def test_new_tables_created() -> None:
    for t in (
        "work_item_dispatches",
        "work_item_events",
        "project_delivery_states",
        "project_members",
        "project_delivery_packages",
    ):
        assert f"create table if not exists {t}" in SQL


def test_extends_not_recreates_existing() -> None:
    assert "create table if not exists projects" not in SQL
    assert "create table if not exists project_work_items" not in SQL
    for col in ("project_key", "environment_scope", "production_allowed", "registry_status"):
        assert f"add column if not exists {col}" in SQL


def test_production_effect_defaults_false_and_indexes() -> None:
    assert "production_effect boolean not null default false" in SQL
    for idx in ("idx_wid_project_id", "idx_wid_status", "idx_wid_correlation_id"):
        assert idx in SQL
    assert "uuid_generate_v4()" in SQL
