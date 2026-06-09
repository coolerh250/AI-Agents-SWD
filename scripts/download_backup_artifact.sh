#!/usr/bin/env bash
# Stage 36 -- off-host backup download.
#
# USAGE:
#   ./scripts/download_backup_artifact.sh <uri> <local_target>
#
# Env: BACKUP_STORAGE_MODE (default local-filesystem). For S3 mode the
# Stage 36 implementation is intentionally skipped (no real S3 client).
#
# Markers:
#   BACKUP_DOWNLOAD: PASS uri=<uri>
#   BACKUP_DOWNLOAD: SKIPPED <reason>
#   BACKUP_DOWNLOAD: FAIL <reason>
set -uo pipefail

uri="${1:-}"
target="${2:-}"

if [ -z "$uri" ] || [ -z "$target" ]; then
  echo "USAGE: $0 <uri> <local_target>"
  echo "BACKUP_DOWNLOAD: FAIL missing_argument"
  exit 1
fi

mode="${BACKUP_STORAGE_MODE:-local-filesystem}"
case "$mode" in
  disabled)
    echo "BACKUP_DOWNLOAD: SKIPPED storage_mode_disabled"
    exit 0
    ;;
  local-filesystem)
    if [ ! -f "$uri" ]; then
      echo "BACKUP_DOWNLOAD: FAIL off_host_artifact_missing"
      exit 1
    fi
    mkdir -p "$(dirname "$target")"
    cp -p "$uri" "$target"
    size=$(wc -c < "$target" | tr -d '[:space:]')
    echo "downloaded_path=$target size_bytes=$size"
    echo "BACKUP_DOWNLOAD: PASS uri=$target"
    exit 0
    ;;
  s3-compatible-placeholder)
    echo "BACKUP_DOWNLOAD: SKIPPED s3_download_not_implemented"
    exit 0
    ;;
  *)
    echo "BACKUP_DOWNLOAD: FAIL unknown_storage_mode=$mode"
    exit 1
    ;;
esac
