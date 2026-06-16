#!/usr/bin/env bash
# Stage 51 -- create a TEST-ONLY backup encryption key file.
#
# The key file lives under a runtime / gitignored path (.runtime/backup-test-key)
# with chmod 600. The raw key is NEVER printed and NEVER committed. Re-runnable:
# an existing key is kept (so checksums / key_id stay stable across a verify run).
#
# Marker: BACKUP_DR_TEST_KEY: PASS / FAIL
set -uo pipefail

cd "$(dirname "$0")/.."

KEY_DIR="${BACKUP_DR_RUNTIME_DIR:-.runtime}"
KEY_FILE="${BACKUP_DR_TEST_KEY_FILE:-$KEY_DIR/backup-test-key}"

mkdir -p "$KEY_DIR"

if [ -s "$KEY_FILE" ]; then
  echo "key file present (kept): $KEY_FILE"
else
  # 48 random bytes, base64. Never echoed.
  openssl rand -base64 48 > "$KEY_FILE" 2>/dev/null || head -c 48 /dev/urandom | base64 > "$KEY_FILE"
  echo "key file created: $KEY_FILE"
fi
chmod 600 "$KEY_FILE" 2>/dev/null || true

# Guard: key file must be gitignored / not tracked.
if git ls-files --error-unmatch "$KEY_FILE" >/dev/null 2>&1; then
  echo "BACKUP_DR_TEST_KEY: FAIL key_file_tracked_by_git"
  exit 1
fi

# Derive an opaque key_id label (sha256 prefix) -- safe to print.
key_id=$(sha256sum "$KEY_FILE" 2>/dev/null | cut -c1-12)
echo "key_id=${key_id:-unknown}"
echo "key_file=$KEY_FILE"
echo "BACKUP_DR_TEST_KEY: PASS"
