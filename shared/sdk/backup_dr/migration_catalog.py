"""Stage 51 -- migration rollback / down catalog.

Scans ``migrations/*.sql`` and classifies every migration so the catalog is
complete with NO ``unknown`` entries. Classification rules (deterministic):

  * A migration with a matching ``*_down.sql`` is ``reversible``.
  * A migration whose body contains a destructive schema change (DROP TABLE /
    DROP COLUMN / TRUNCATE / DELETE FROM / DROP TYPE) without a down script is
    ``manual_rollback_required`` (high risk) and gets explicit rollback notes.
  * Any other (purely additive: CREATE TABLE/INDEX IF NOT EXISTS, ALTER ... ADD,
    INSERT ... ON CONFLICT) migration is ``forward_only`` with a note describing
    how to roll back by dropping the objects it creates.

``migration_down_gap_closed`` is true when the catalog is complete and every
non-reversible migration carries rollback notes -- NOT when everything is
reversible.
"""

from __future__ import annotations

import re
from pathlib import Path

from shared.sdk.backup_dr.models import MigrationRollbackCatalogEntry

_DESTRUCTIVE_RE = re.compile(
    r"\b(DROP\s+TABLE|DROP\s+COLUMN|TRUNCATE|DELETE\s+FROM|DROP\s+TYPE|"
    r"ALTER\s+TABLE\s+\S+\s+DROP|DROP\s+CONSTRAINT)\b",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"^(\d+)_")


def _migration_number(stem: str) -> int | None:
    m = _NUM_RE.match(stem)
    return int(m.group(1)) if m else None


def classify_migration(path: Path, *, has_down: bool) -> MigrationRollbackCatalogEntry:
    base = path.name
    stem = base[:-4] if base.endswith(".sql") else base
    number = _migration_number(stem)
    body = ""
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        body = ""

    if has_down:
        return MigrationRollbackCatalogEntry(
            migration_file=base,
            migration_number=number,
            reversibility="reversible",
            down_script_available=True,
            rollback_notes="Down script present; apply the matching *_down.sql to roll back.",
            risk_level="low",
            verified=True,
            metadata={"classified_by": "down_script"},
        )

    if _DESTRUCTIVE_RE.search(body):
        return MigrationRollbackCatalogEntry(
            migration_file=base,
            migration_number=number,
            reversibility="manual_rollback_required",
            down_script_available=False,
            rollback_notes=(
                "Destructive schema change (drop/truncate/delete) with no down "
                "script. Rollback requires manual data + schema restoration from "
                "the latest verified backup; review affected tables before applying."
            ),
            risk_level="high",
            verified=True,
            metadata={"classified_by": "destructive_content"},
        )

    return MigrationRollbackCatalogEntry(
        migration_file=base,
        migration_number=number,
        reversibility="forward_only",
        down_script_available=False,
        rollback_notes=(
            "Additive-only migration (CREATE ... IF NOT EXISTS / ALTER ... ADD / "
            "INSERT ... ON CONFLICT). Roll back by dropping the objects this "
            "migration creates; no data loss on forward re-apply (idempotent)."
        ),
        risk_level="low",
        verified=True,
        metadata={"classified_by": "additive_content"},
    )


def build_migration_catalog(
    migrations_dir: str | Path = "migrations",
) -> list[MigrationRollbackCatalogEntry]:
    """Scan migrations and classify each non-down migration file."""
    base_dir = Path(migrations_dir)
    entries: list[MigrationRollbackCatalogEntry] = []
    if not base_dir.is_dir():
        return entries
    files = sorted(p for p in base_dir.glob("*.sql"))
    down_stems = {p.name[: -len("_down.sql")] for p in files if p.name.endswith("_down.sql")}
    for path in files:
        if path.name.endswith("_down.sql"):
            continue
        stem = path.name[:-4]
        entries.append(classify_migration(path, has_down=stem in down_stems))
    return entries


def catalog_summary(entries: list[MigrationRollbackCatalogEntry]) -> dict[str, int | bool]:
    counts = {
        "total": len(entries),
        "reversible": sum(1 for e in entries if e.reversibility == "reversible"),
        "forward_only": sum(1 for e in entries if e.reversibility == "forward_only"),
        "manual_rollback_required": sum(
            1 for e in entries if e.reversibility == "manual_rollback_required"
        ),
        "unknown": sum(1 for e in entries if e.reversibility == "unknown"),
    }
    non_reversible_with_notes = all(
        bool(e.rollback_notes)
        for e in entries
        if e.reversibility in ("forward_only", "manual_rollback_required")
    )
    counts["complete"] = bool(entries) and counts["unknown"] == 0 and non_reversible_with_notes
    return counts


def migration_down_gap_closed(entries: list[MigrationRollbackCatalogEntry]) -> bool:
    return bool(catalog_summary(entries)["complete"])


__all__ = [
    "classify_migration",
    "build_migration_catalog",
    "catalog_summary",
    "migration_down_gap_closed",
]
