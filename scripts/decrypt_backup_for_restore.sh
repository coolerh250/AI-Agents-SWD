#!/usr/bin/env bash
# Stage 36 -- decrypt an encrypted backup artifact for a restore drill.
#
# USAGE:
#   ./scripts/decrypt_backup_for_restore.sh <encrypted_artifact> <output_path>
#
# Inputs:
#   BACKUP_ENCRYPTION_KEY  -- env-mode key (production path)
#   BACKUP_KEY_FILE        -- absolute path to a test-only keyfile
#                             (only honored when BACKUP_KEY_SOURCE=test-only-generated)
#
# Hard rules:
#   * Only decrypts to a path that is NOT inside ./backups/aiagents-*.dump
#     (the encrypted side) unless explicitly different.
#   * Never echoes / logs the key value.
#   * Marker on success: BACKUP_DECRYPT: PASS
set -uo pipefail

in_path="${1:-}"
out_path="${2:-}"

if [ -z "$in_path" ] || [ -z "$out_path" ]; then
  echo "USAGE: $0 <encrypted_artifact> <output_path>"
  echo "BACKUP_DECRYPT: FAIL (missing argument)"
  exit 1
fi

if [ ! -f "$in_path" ]; then
  echo "BACKUP_DECRYPT: FAIL (encrypted artifact not found: $in_path)"
  exit 1
fi

# Refuse to overwrite an existing output unless explicitly requested.
if [ -e "$out_path" ] && [ "${BACKUP_DECRYPT_OVERWRITE:-false}" != "true" ]; then
  echo "BACKUP_DECRYPT: FAIL (output already exists: $out_path -- set BACKUP_DECRYPT_OVERWRITE=true to replace)"
  exit 1
fi

mkdir -p "$(dirname "$out_path")"

if [ -n "${BACKUP_ENCRYPTION_KEY:-}" ]; then
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -pass env:BACKUP_ENCRYPTION_KEY \
    -in "$in_path" -out "$out_path" 2>/dev/null
  rc=$?
elif [ "${BACKUP_KEY_SOURCE:-}" = "test-only-generated" ] && [ -n "${BACKUP_KEY_FILE:-}" ]; then
  if [ ! -f "$BACKUP_KEY_FILE" ]; then
    echo "BACKUP_DECRYPT: FAIL (test keyfile not found)"
    exit 1
  fi
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -pass file:"$BACKUP_KEY_FILE" \
    -in "$in_path" -out "$out_path" 2>/dev/null
  rc=$?
else
  echo "BACKUP_DECRYPT: FAIL (no key source -- set BACKUP_ENCRYPTION_KEY or BACKUP_KEY_FILE+BACKUP_KEY_SOURCE=test-only-generated)"
  exit 1
fi

if [ "$rc" -ne 0 ]; then
  echo "BACKUP_DECRYPT: FAIL (openssl dec rc=$rc)"
  rm -f "$out_path"
  exit "$rc"
fi

size=$(wc -c < "$out_path" | tr -d '[:space:]')
echo "decrypted_path=$out_path size_bytes=$size"
echo "BACKUP_DECRYPT: PASS"
