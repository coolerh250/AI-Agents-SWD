#!/usr/bin/env bash
# Stage 43 -- controlled restore of a single test-tampered audit_logs.summary.
#
# DRY-RUN BY DEFAULT. Modifies audit_logs.summary for exactly one record so it
# re-matches its already-correct integrity record. Modifies ZERO
# audit_integrity_records and does NOT cascade the chain.
#
# Gates (all required to make a DB change):
#   1. source/audit-forensics/audit_forensic_latest.json exists.
#   2. forensic root_cause == test_tamper_not_restored, repair_allowed == true,
#      repair_risk == low, production_executed == false.
#   3. AUDIT_LOG_RESTORE_APPROVED == true   (explicit operator flag).
#   4. removing the proven tamper marker reproduces the stored canonical hash.
#
# A snapshot is taken before an approved apply. The restore action is recorded
# as a new audit row whose integrity record is appended to the chain tail.
#
# Writes:
#   source/audit-forensics/audit_log_restore_{timestamp}.json
#   source/audit-forensics/audit_log_restore_latest.json
#
# Marker: AUDIT_LOG_RESTORE: DRY_RUN / APPROVAL_REQUIRED / REJECTED_UNSAFE /
#         COMPLETED / FAILED

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
REPORT="source/audit-forensics/audit_forensic_latest.json"
APPROVED="${AUDIT_LOG_RESTORE_APPROVED:-false}"

echo "### restore_audit_log_test_tamper_residue: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  approved_flag=${APPROVED}"

if [ ! -f "$REPORT" ]; then
    echo "no forensic report at $REPORT -- run analyze_audit_chain_mismatch.py first"
    echo "AUDIT_LOG_RESTORE: REJECTED_UNSAFE"
    exit 0
fi

# Snapshot before an approved apply (best-effort).
if [ "$APPROVED" = "true" ]; then
    bash scripts/export_audit_forensic_snapshot.sh >/dev/null 2>&1 || true
fi

AUDIT_LOG_RESTORE_APPROVED="$APPROVED" "$PY" - "$REPORT" <<'PY'
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

from shared.sdk.audit_integrity.log_restore import (  # noqa: E402
    AuditLogRestorer,
    RESTORE_STATUS_COMPLETED,
)
from shared.sdk.audit_integrity.verifier import AuditChainVerifier  # noqa: E402

REPORT = sys.argv[1]
APPROVED = os.environ.get("AUDIT_LOG_RESTORE_APPROVED", "false").strip().lower() == "true"
DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
EXPLICIT_ID = os.environ.get("AUDIT_LOG_RESTORE_AUDIT_LOG_ID") or None
EXPLICIT_SEQ = os.environ.get("AUDIT_LOG_RESTORE_SEQUENCE")
EXPLICIT_SEQ = int(EXPLICIT_SEQ) if EXPLICIT_SEQ else None


async def main() -> int:
    forensic = json.loads(Path(REPORT).read_text(encoding="utf-8"))
    restorer = AuditLogRestorer(dsn=DSN)
    precheck = await restorer.precheck(
        forensic, audit_log_id=EXPLICIT_ID, sequence_number=EXPLICIT_SEQ
    )

    dry_run = not (APPROVED and precheck.ok)
    result = await restorer.apply(precheck, approved=APPROVED, dry_run=dry_run)

    # After a completed restore, run the full verifier (separate connection,
    # sees the committed state).
    if result.get("status") == RESTORE_STATUS_COMPLETED:
        try:
            vr = await AuditChainVerifier(dsn=DSN).verify_chain()
            result["verifier_after_restore"] = {
                "status": vr.status,
                "first_failure_sequence": vr.first_failure_sequence,
                "failure_reason": vr.failure_reason,
            }
        except Exception as exc:  # pragma: no cover
            result.setdefault("warnings", []).append(
                f"post-restore verify error: {exc.__class__.__name__}"
            )

    ts = datetime.now(timezone.utc)
    restore_id = f"audit_log_restore_{ts.strftime('%Y%m%d_%H%M%S')}"
    result["restore_id"] = restore_id
    result["forensic_report_id"] = forensic.get("report_id")
    result["full_regression_after_restore"] = None  # set by the verify script
    result["precheck"] = precheck.to_dict()

    out_dir = Path("source/audit-forensics")
    out_dir.mkdir(parents=True, exist_ok=True)
    serialised = json.dumps(result, indent=2, ensure_ascii=False)
    (out_dir / f"{restore_id}.json").write_text(serialised, encoding="utf-8")
    (out_dir / "audit_log_restore_latest.json").write_text(serialised, encoding="utf-8")

    print(f"restore_id={restore_id}")
    print(f"affected_audit_log_id={result['affected_audit_log_id']}")
    print(f"affected_sequence_number={result['affected_sequence_number']}")
    print(f"root_cause={result['root_cause']}")
    print(f"dry_run={result['dry_run']}")
    print(f"approved={result['approved']}")
    print(f"hash_match_after={result['hash_match_after']}")
    print(f"audit_logs_modified_count={result['audit_logs_modified_count']}")
    print(
        "audit_integrity_records_modified_count="
        f"{result['audit_integrity_records_modified_count']}"
    )
    print(f"before_contains_tamper_marker={result['before_contains_tamper_marker']}")
    print(f"after_contains_tamper_marker={result['after_contains_tamper_marker']}")
    vr = result.get("verifier_after_restore")
    if vr:
        print(f"verifier_after_restore={vr.get('status')}")
    print(f"status={result['status']}")
    print(f"AUDIT_LOG_RESTORE: {result['status'].upper()}")
    return 0


raise SystemExit(asyncio.run(main()))
PY