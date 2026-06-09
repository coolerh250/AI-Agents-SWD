#!/usr/bin/env bash
# Stage 36 -- migration down-script inventory.
#
# Walks ./migrations/*.sql and reports which ones do NOT have a
# matching *_down.sql. Stage 36 does NOT require every migration to
# have a down script; it merely produces an inventory that operators
# can use to triage which migrations carry the most rollback risk.
#
# Markers:
#   MIGRATION_DOWN_SCRIPT_INVENTORY: PASS_WITH_GAPS gaps=<N>
#   MIGRATION_DOWN_SCRIPT_INVENTORY: PASS  (when every migration has a down)
set -uo pipefail

MIGRATIONS_DIR="${MIGRATIONS_DIR:-migrations}"
if [ ! -d "$MIGRATIONS_DIR" ]; then
  echo "MIGRATION_DOWN_SCRIPT_INVENTORY: FAIL migrations_dir_missing"
  exit 1
fi

total=0
with_down=0
gaps=0
gap_list=""

for f in "$MIGRATIONS_DIR"/*.sql; do
  base=$(basename "$f")
  case "$base" in
    *_down.sql) continue ;;
  esac
  total=$((total + 1))
  stem="${base%.sql}"
  down="$MIGRATIONS_DIR/${stem}_down.sql"
  if [ -f "$down" ]; then
    with_down=$((with_down + 1))
  else
    gaps=$((gaps + 1))
    gap_list="${gap_list}${base},"
  fi
done

gap_list="${gap_list%,}"

echo "migration_down_inventory_begin"
echo "total=$total"
echo "with_down=$with_down"
echo "gaps=$gaps"
echo "gap_list=$gap_list"
echo "migration_down_inventory_end"

if [ "$gaps" -eq 0 ]; then
  echo "MIGRATION_DOWN_SCRIPT_INVENTORY: PASS"
else
  echo "MIGRATION_DOWN_SCRIPT_INVENTORY: PASS_WITH_GAPS gaps=$gaps"
fi
