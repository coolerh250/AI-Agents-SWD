#!/usr/bin/env bash
# Stage 42 -- controlled audit chain integrity repair.
#
# DRY-RUN BY DEFAULT. This script repairs audit_integrity_records ONLY; it
# never modifies, deletes, or reorders audit_logs.
#
# Gates (all must hold to make any DB change):
#   1. source/audit-forensics/audit_forensic_latest.json exists.
#   2. report.repair_allowed == true.
#   3. AUDIT_CHAIN_REPAIR_APPROVED == true   (explicit operator flag).
#
# When 2 or 3 are not met the script makes NO DB change and reports the
# dry-run / skipped-unsafe outcome.
#
# Before an approved apply it writes a redacted snapshot. After an apply it
# re-verifies inside the same transaction and rolls back on any mismatch.
#
# Writes:
#   source/audit-forensics/audit_repair_{timestamp}.json
#   source/audit-forensics/audit_repair_latest.json
#
# Marker: AUDIT_CHAIN_REPAIR: DRY_RUN / SKIPPED_UNSAFE / APPROVAL_REQUIRED /
#         COMPLETED / FAILED

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
REPORT="source/audit-forensics/audit_forensic_latest.json"
APPROVED="${AUDIT_CHAIN_REPAIR_APPROVED:-false}"

echo "### repair_audit_chain_integrity: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  approved_flag=${APPROVED}"

if [ ! -f "$REPORT" ]; then
    echo "no forensic report at $REPORT -- run analyze_audit_chain_mismatch.py first"
    echo "AUDIT_CHAIN_REPAIR: SKIPPED_UNSAFE"
    exit 0
fi

# Take a redacted snapshot before any approved apply (best-effort).
if [ "$APPROVED" = "true" ]; then
    bash scripts/export_audit_forensic_snapshot.sh >/dev/null 2>&1 || true
fi

AUDIT_CHAIN_REPAIR_APPROVED="$APPROVED" "$PY" - "$REPORT" <<'PY'
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

import asyncpg  # noqa: E402

from shared.sdk.audit_integrity.forensics import (  # noqa: E402
    AuditChainForensicAnalyzer,
    classify_chain_root_cause,
)
from shared.sdk.audit_integrity.models import CHAIN_VERSION  # noqa: E402
from shared.sdk.audit_integrity.repair import (  # noqa: E402
    AuditChainRepairer,
    REPAIR_STATUS_COMPLETED,
    plan_repair,
)
from shared.sdk.audit_integrity.audit_events import (  # noqa: E402
    DECISION_AUDIT_CHAIN_REPAIR_COMPLETED,
)

REPORT = sys.argv[1]
APPROVED = os.environ.get("AUDIT_CHAIN_REPAIR_APPROVED", "false").strip().lower() == "true"
DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")


async def emit_repair_event(report: dict) -> str | None:
    """Insert an audit_chain_repair_completed row + its integrity record.

    Keeps the repair action itself inside the tamper-evident chain. Only
    called after a COMPLETED apply. Never references a key value.
    """
    from shared.sdk.audit_integrity.store import create_integrity_record_in_txn
    from shared.sdk.audit_integrity.signer import AuditSigner

    refs = {
        "repair_id": report.get("repair_id"),
        "root_cause": report.get("root_cause"),
        "changed_records_count": report.get("changed_records_count"),
        "production_executed": False,
    }
    conn = await asyncpg.connect(dsn=DSN, timeout=10)
    try:
        async with conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO audit_logs (agent, decision_type, summary, result, "
                "task_id, artifact_refs) VALUES ($1, $2, $3, $4, $5, $6::jsonb) "
                "RETURNING id, task_id, agent, decision_type, summary, result, "
                "artifact_refs, created_at",
                "orchestrator",
                DECISION_AUDIT_CHAIN_REPAIR_COMPLETED,
                "audit chain integrity repair completed",
                "completed",
                "audit-chain-repair",
                json.dumps(refs),
            )
            audit_log_row = {
                "audit_log_id": str(row["id"]),
                "task_id": row["task_id"],
                "agent": row["agent"],
                "decision_type": row["decision_type"],
                "summary": row["summary"],
                "result": row["result"],
                "artifact_refs": row["artifact_refs"],
                "created_at": row["created_at"],
            }
            await create_integrity_record_in_txn(
                conn, audit_log_row=audit_log_row, signer=AuditSigner()
            )
            return str(row["id"])
    finally:
        await conn.close()


async def main() -> int:
    report_in = json.loads(Path(REPORT).read_text(encoding="utf-8"))
    analyzer = AuditChainForensicAnalyzer(dsn=DSN)
    failed = await analyzer.scan(chain_version=CHAIN_VERSION)
    classification = classify_chain_root_cause(failed)

    repairer = AuditChainRepairer(dsn=DSN)
    tail = await repairer.chain_tail_sequence(chain_version=CHAIN_VERSION)
    plan = plan_repair(
        failed=failed,
        root_cause=classification.get("root_cause_classification") or "unknown",
        repair_allowed=bool(classification.get("repair_allowed")),
        repair_risk=classification.get("repair_risk") or "high",
        chain_tail_sequence=tail,
        reason=classification.get("repair_policy_reason") or "",
    )

    # dry_run is True unless the operator approved AND repair is allowed.
    dry_run = not (APPROVED and plan.repair_allowed)
    result = await repairer.apply(
        plan, approved=APPROVED, dry_run=dry_run, chain_version=CHAIN_VERSION
    )

    ts = datetime.now(timezone.utc)
    repair_id = f"audit_repair_{ts.strftime('%Y%m%d_%H%M%S')}"
    result["repair_id"] = repair_id
    result["forensic_report_id"] = report_in.get("report_id")
    result["affected_sequences"] = plan.to_dict().get("affected_sequence_range")
    result["audit_repair_event_id"] = None
    result["rollback_needed"] = result.get("status") == "failed"

    if result.get("status") == REPAIR_STATUS_COMPLETED:
        try:
            result["audit_repair_event_id"] = await emit_repair_event(result)
        except Exception as exc:  # pragma: no cover - best effort
            result.setdefault("warnings", []).append(
                f"repair event emission failed: {exc.__class__.__name__}"
            )

    out_dir = Path("source/audit-forensics")
    out_dir.mkdir(parents=True, exist_ok=True)
    serialised = json.dumps(result, indent=2, ensure_ascii=False)
    (out_dir / f"{repair_id}.json").write_text(serialised, encoding="utf-8")
    (out_dir / "audit_repair_latest.json").write_text(serialised, encoding="utf-8")

    print(f"repair_id={repair_id}")
    print(f"root_cause={result['root_cause']}")
    print(f"repair_allowed={result['repair_allowed']}")
    print(f"dry_run={result['dry_run']}")
    print(f"approved={result['approved']}")
    print(f"audit_logs_modified={result['audit_logs_modified']}")
    print(f"audit_integrity_records_modified={result['audit_integrity_records_modified']}")
    print(f"changed_records_count={result['changed_records_count']}")
    print(f"status={result['status']}")
    print(f"AUDIT_CHAIN_REPAIR: {result['status'].upper()}")
    return 0


raise SystemExit(asyncio.run(main()))
PY