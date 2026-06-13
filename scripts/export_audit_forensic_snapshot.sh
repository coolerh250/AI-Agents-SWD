#!/usr/bin/env bash
# Stage 42 -- export a redacted forensic snapshot of the affected audit rows.
#
# Reads source/audit-forensics/audit_forensic_latest.json, then for every
# failed sequence exports:
#   * the affected audit_integrity_records row
#   * the corresponding audit_logs row
#   * the previous and next N records (default N=5)
# as REDACTED JSON into source/audit-forensics/snapshots/.
#
# The snapshot may contain full (redacted) payload and is therefore
# gitignored -- the forensic *report* is safe to commit, the snapshot is not.
#
# READ-ONLY. Never mutates the DB. Never emits a secret / key value.
#
# Marker: AUDIT_FORENSIC_SNAPSHOT: WRITTEN / SKIPPED / ERROR

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
NEIGHBORS="${SNAPSHOT_NEIGHBORS:-5}"
REPORT="source/audit-forensics/audit_forensic_latest.json"

if [ ! -f "$REPORT" ]; then
    echo "no forensic report at $REPORT -- run analyze_audit_chain_mismatch.py first"
    echo "AUDIT_FORENSIC_SNAPSHOT: SKIPPED"
    exit 0
fi

SNAPSHOT_NEIGHBORS="$NEIGHBORS" "$PY" - "$REPORT" <<'PY'
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())
import asyncpg  # noqa: E402

REPORT = sys.argv[1]
N = int(os.environ.get("SNAPSHOT_NEIGHBORS", "5"))
DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")

SECRET = re.compile(r"(ghp_[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{8,}|xox[baprs]-[A-Za-z0-9-]{8,})")


def scrub(value):
    if isinstance(value, str):
        return SECRET.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if _is_secret_key(k) else scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(t in k for t in ("token", "secret", "api_key", "apikey", "hmac_key", "password"))


async def main():
    report = json.loads(Path(REPORT).read_text(encoding="utf-8"))
    seqs = sorted(set(report.get("failed_sequences") or []))
    if not seqs:
        print("AUDIT_FORENSIC_SNAPSHOT: SKIPPED (no failed sequences)")
        return 0
    wanted = set()
    for s in seqs:
        for d in range(-N, N + 1):
            if s + d >= 1:
                wanted.add(s + d)
    conn = await asyncpg.connect(dsn=DSN, timeout=10)
    try:
        rows = await conn.fetch(
            "SELECT r.sequence_number, r.integrity_id, r.audit_log_id, r.prev_hash, "
            "r.row_hash, r.canonical_payload_hash, r.signature_status, r.integrity_status, "
            "al.task_id, al.agent, al.decision_type, al.summary, al.result, "
            "al.artifact_refs, al.created_at "
            "FROM audit_integrity_records r JOIN audit_logs al ON al.id = r.audit_log_id "
            "WHERE r.sequence_number = ANY($1::bigint[]) ORDER BY r.sequence_number ASC",
            sorted(wanted),
        )
    finally:
        await conn.close()

    records = []
    for row in rows:
        refs = row["artifact_refs"]
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except (TypeError, ValueError):
                refs = {}
        records.append(
            {
                "sequence_number": int(row["sequence_number"]),
                "integrity_id": str(row["integrity_id"]),
                "audit_log_id": str(row["audit_log_id"]),
                "prev_hash": row["prev_hash"],
                "row_hash": row["row_hash"],
                "canonical_payload_hash": row["canonical_payload_hash"],
                "signature_status": row["signature_status"],
                "integrity_status": row["integrity_status"],
                "is_failed_sequence": int(row["sequence_number"]) in set(seqs),
                "task_id": row["task_id"],
                "agent": row["agent"],
                "decision_type": row["decision_type"],
                "summary": scrub(row["summary"]),
                "result": row["result"],
                "artifact_refs": scrub(refs),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )

    ts = datetime.now(timezone.utc)
    snapshot = {
        "snapshot_id": f"audit_snapshot_{ts.strftime('%Y%m%d_%H%M%S')}",
        "created_at": ts.isoformat(),
        "forensic_report_id": report.get("report_id"),
        "failed_sequences": seqs,
        "neighbors": N,
        "records": records,
        "production_executed": bool(report.get("production_executed")),
    }
    out_dir = Path("source/audit-forensics/snapshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{snapshot['snapshot_id']}.json"
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"snapshot_path={out_path}")
    print(f"records_exported={len(records)}")
    print("AUDIT_FORENSIC_SNAPSHOT: WRITTEN")
    return 0


raise SystemExit(asyncio.run(main()))
PY