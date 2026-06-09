#!/usr/bin/env bash
# Stage 36 -- remove the AI-Agents-SWD backup cron entry (if any).
#
# Idempotent. Marker: BACKUP_SCHEDULE_UNINSTALLED: PASS
set -uo pipefail

tmpfile=$(mktemp /tmp/aiagents-backup-cron-uninstall.XXXXXX)
crontab -l 2>/dev/null > "$tmpfile" || true
grep -v 'backup_postgres_encrypted.sh' "$tmpfile" > "${tmpfile}.new" || true

if ! diff -q "$tmpfile" "${tmpfile}.new" >/dev/null 2>&1; then
  crontab "${tmpfile}.new"
  echo "removed backup cron entries"
else
  echo "no backup cron entries to remove"
fi
rm -f "$tmpfile" "${tmpfile}.new"
echo "BACKUP_SCHEDULE_UNINSTALLED: PASS"
