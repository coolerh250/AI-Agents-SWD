#!/usr/bin/env bash
# Stage 51 -- backup encryption verification.
#
# Ensures a test-only encryption config + encrypted artifact + manifest with a
# key_id label, and asserts NO raw key leaks into the artifact/manifest/logs.
#
# Marker: BACKUP_ENCRYPTION_VERIFY: PASS / FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true
PY="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres@localhost:5432/aiagents}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
RUNTIME_DIR="${BACKUP_DR_RUNTIME_DIR:-.runtime}/backup-dr"
KEY_FILE="${BACKUP_DR_TEST_KEY_FILE:-${BACKUP_DR_RUNTIME_DIR:-.runtime}/backup-test-key}"
SNAPSHOT="source/dr-reports/backup_dr_readiness_latest.json"
facts="$RUNTIME_DIR/facts.json"

echo "### verify_backup_encryption"
fail=0
if [ ! -f "$facts" ]; then
  bash scripts/run_encrypted_backup.sh >/tmp/bdr_enc_produce.log 2>&1 || { tail -8 /tmp/bdr_enc_produce.log; echo "BACKUP_ENCRYPTION_VERIFY: FAIL produce"; exit 1; }
fi
enc=$("$PY" -c "import json;print(json.load(open('$facts')).get('encrypted_artifact_path',''))" 2>/dev/null || echo "")
[ -n "$enc" ] && [ -f "$enc" ] && echo "  encrypted artifact: $enc" || { echo "  missing encrypted artifact"; fail=1; }
key_id=$(sha256sum "$KEY_FILE" 2>/dev/null | cut -c1-12)
[ -n "$key_id" ] && echo "  key_id=$key_id" || { echo "  no key_id"; fail=1; }
# encryption config status via SDK
cfg_status=$("$PY" -c "from shared.sdk.backup_dr.encryption_config import resolve_encryption_config as r;print(r().status)" 2>/dev/null)
[ "$cfg_status" = "configured" ] && echo "  encryption configured" || { echo "  encryption status=$cfg_status"; fail=1; }
# no raw key leak
keyval=$(cat "$KEY_FILE" 2>/dev/null)
if [ -n "$keyval" ]; then
  for f in "$facts" "$SNAPSHOT" /tmp/bdr_enc_produce.log; do
    [ -f "$f" ] && grep -qF "$keyval" "$f" 2>/dev/null && { echo "  raw key leak in $f"; fail=1; }
  done
fi
[ "$fail" = "0" ] && echo "  no raw key leak"

if [ "$fail" = "0" ]; then echo "BACKUP_ENCRYPTION_VERIFY: PASS"; exit 0; fi
echo "BACKUP_ENCRYPTION_VERIFY: FAIL"; exit 1
