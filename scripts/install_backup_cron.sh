#!/usr/bin/env bash
# Stage 36 -- backup scheduling baseline (dry-run by default).
#
# This script DOES NOT install a cron entry unless INSTALL_BACKUP_SCHEDULE=true.
# It always prints the proposed cron line + crontab file path so an
# operator can review it.
#
# Markers:
#   BACKUP_SCHEDULE_DRY_RUN: PASS  -- proposed schedule rendered (default)
#   BACKUP_SCHEDULE_INSTALLED: PASS -- entry installed (operator-opt-in)
#   BACKUP_SCHEDULE: FAIL <reason>
set -uo pipefail

REPO_ROOT="$(pwd)"
SCHEDULE_CRON="${BACKUP_SCHEDULE_CRON:-0 2 * * *}"   # daily 02:00 UTC by default
SCHEDULE_LOG_DIR="${SCHEDULE_LOG_DIR:-source/runtime-health}"
SCHEDULE_LOG_PATH="${SCHEDULE_LOG_PATH:-$SCHEDULE_LOG_DIR/backup_schedule.log}"
SCHEDULE_USER="${SCHEDULE_USER:-$(whoami)}"

mkdir -p "$SCHEDULE_LOG_DIR"

backup_cmd="cd ${REPO_ROOT} && ./scripts/backup_postgres_encrypted.sh >> ${SCHEDULE_LOG_PATH} 2>&1"
cron_line="${SCHEDULE_CRON} ${backup_cmd}"

echo "### install_backup_cron"
echo "user=$SCHEDULE_USER"
echo "cron_line=$cron_line"

if [ "${INSTALL_BACKUP_SCHEDULE:-false}" != "true" ]; then
  echo "(dry-run -- set INSTALL_BACKUP_SCHEDULE=true to actually install)"
  echo "BACKUP_SCHEDULE_DRY_RUN: PASS"
  exit 0
fi

# Real install path -- only entered when operator opts in.
tmpfile=$(mktemp /tmp/aiagents-backup-cron.XXXXXX)
crontab -l 2>/dev/null > "$tmpfile" || true
# Strip any existing AI-Agents-SWD backup line to keep idempotency.
grep -v 'backup_postgres_encrypted.sh' "$tmpfile" > "${tmpfile}.new" || true
echo "$cron_line" >> "${tmpfile}.new"
crontab "${tmpfile}.new"
rc=$?
rm -f "$tmpfile" "${tmpfile}.new"
if [ "$rc" -ne 0 ]; then
  echo "BACKUP_SCHEDULE: FAIL crontab_install_rc=$rc"
  exit "$rc"
fi
echo "BACKUP_SCHEDULE_INSTALLED: PASS"
