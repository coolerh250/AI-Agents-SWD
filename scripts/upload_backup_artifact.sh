#!/usr/bin/env bash
# Stage 36 -- off-host backup upload (skipped-by-default).
#
# USAGE:
#   ./scripts/upload_backup_artifact.sh <artifact_path> <backup_id>
#
# Env:
#   BACKUP_STORAGE_MODE -- 'local-filesystem' (default) | 's3-compatible-placeholder' | 'disabled'
#   BACKUP_STORAGE_BUCKET, BACKUP_STORAGE_PREFIX, BACKUP_STORAGE_ENDPOINT
#   BACKUP_STORAGE_ACCESS_KEY_ID, BACKUP_STORAGE_SECRET_ACCESS_KEY
#
# Markers:
#   BACKUP_UPLOAD: SKIPPED <reason>
#   BACKUP_UPLOAD: PASS uri=<uri>
#   BACKUP_UPLOAD: FAIL <reason>
#
# Never echoes credential values.
set -uo pipefail

artifact="${1:-}"
backup_id="${2:-}"

if [ -z "$artifact" ] || [ -z "$backup_id" ]; then
  echo "USAGE: $0 <artifact_path> <backup_id>"
  echo "BACKUP_UPLOAD: FAIL missing_argument"
  exit 1
fi

if [ ! -f "$artifact" ]; then
  echo "BACKUP_UPLOAD: FAIL artifact_missing"
  exit 1
fi

mode="${BACKUP_STORAGE_MODE:-local-filesystem}"
echo "step=upload mode=$mode artifact=$artifact backup_id=$backup_id"

case "$mode" in
  disabled)
    echo "BACKUP_UPLOAD: SKIPPED storage_mode_disabled"
    exit 0
    ;;
  local-filesystem)
    bucket="${BACKUP_STORAGE_BUCKET:-}"
    prefix="${BACKUP_STORAGE_PREFIX:-$backup_id}"
    if [ -z "$bucket" ]; then
      echo "BACKUP_UPLOAD: SKIPPED credential_missing"
      exit 0
    fi
    mkdir -p "$bucket/$prefix"
    target="$bucket/$prefix/$(basename "$artifact")"
    cp -p "$artifact" "$target"
    size=$(wc -c < "$target" | tr -d '[:space:]')
    echo "uri=$target bytes_transferred=$size"
    echo "BACKUP_UPLOAD: PASS uri=$target"
    exit 0
    ;;
  s3-compatible-placeholder)
    bucket="${BACKUP_STORAGE_BUCKET:-}"
    have_access=true
    have_secret=true
    [ -z "${BACKUP_STORAGE_ACCESS_KEY_ID:-}" ] && have_access=false
    [ -z "${BACKUP_STORAGE_SECRET_ACCESS_KEY:-}" ] && have_secret=false
    if [ -z "$bucket" ] || [ "$have_access" = "false" ] || [ "$have_secret" = "false" ]; then
      echo "BACKUP_UPLOAD: SKIPPED credential_missing"
      exit 0
    fi
    # Stage 36 intentionally does NOT ship a real S3 upload. Mark
    # 'skipped' with a precise reason so a future stage can drop in
    # boto3 without changing the interface.
    echo "BACKUP_UPLOAD: SKIPPED s3_upload_not_implemented"
    exit 0
    ;;
  *)
    echo "BACKUP_UPLOAD: FAIL unknown_storage_mode=$mode"
    exit 1
    ;;
esac
