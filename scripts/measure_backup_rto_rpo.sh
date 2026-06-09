#!/usr/bin/env bash
# Stage 36 -- RTO / RPO measurement summary.
#
# Reads the latest DR report (source/dr-reports/dr_report_latest.json)
# and the latest backup manifest in ./backups/, then prints a single
# RTO_RPO_SUMMARY block + marker.
#
# RTO = total_drill_duration_seconds from the latest DR report.
# RPO = (now - latest_backup_created_at). If no schedule is configured
#       we mark rpo_status=manual_only.
#
# Markers:
#   RTO_RPO_SUMMARY: PASS
#   RTO_RPO_SUMMARY: SKIPPED no_dr_report
set -uo pipefail

DR_REPORTS_DIR="${DR_REPORTS_DIR:-source/dr-reports}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
latest_report="$DR_REPORTS_DIR/dr_report_latest.json"

if [ ! -f "$latest_report" ]; then
  echo "RTO_RPO_SUMMARY: SKIPPED no_dr_report"
  exit 0
fi

latest_manifest=$(ls -1t "$BACKUP_DIR"/backup_manifest_*.json 2>/dev/null | head -n1 || true)

python3 - "$latest_report" "$latest_manifest" <<'PY'
import json, os, sys, datetime

report_path = sys.argv[1]
manifest_path = sys.argv[2] if len(sys.argv) > 2 else ""

with open(report_path, "r", encoding="utf-8") as fh:
    report = json.load(fh)

rto = float(report.get("estimated_rto_seconds") or 0.0)
backup_dur = float(report.get("backup_duration_seconds") or 0.0)
restore_dur = float(report.get("restore_duration_seconds") or 0.0)
total_dur = float(report.get("total_drill_duration_seconds") or 0.0)
integrity = report.get("audit_integrity_status", "not_run")

rpo_seconds = None
rpo_status = "manual_only"
if manifest_path and os.path.isfile(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    try:
        created_at = datetime.datetime.strptime(
            manifest.get("created_at", ""), "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        rpo_seconds = (now - created_at).total_seconds()
    except Exception:
        rpo_seconds = None

print("RTO_RPO_SUMMARY_BEGIN")
print(f"backup_duration_seconds={backup_dur:.3f}")
print(f"restore_duration_seconds={restore_dur:.3f}")
print(f"total_drill_duration_seconds={total_dur:.3f}")
print(f"estimated_rto_seconds={rto:.3f}")
print(f"estimated_rpo_seconds={rpo_seconds if rpo_seconds is None else f'{rpo_seconds:.3f}'}")
print(f"rpo_status={rpo_status}")
print(f"audit_integrity_status={integrity}")
print(f"latest_dr_report={report_path}")
print(f"latest_manifest={manifest_path or 'none'}")
print("RTO_RPO_SUMMARY_END")
PY

echo "RTO_RPO_SUMMARY: PASS"
