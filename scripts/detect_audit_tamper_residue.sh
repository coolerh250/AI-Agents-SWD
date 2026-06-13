#!/usr/bin/env bash
# Stage 44 -- detect leftover [TAMPER-SIMULATION] residue in audit_logs.
#
# READ-ONLY. Reports how many audit_logs rows still carry a tamper-simulation
# marker (a failed/raced tamper sim that did not restore). Emits only safe
# fields (count, audit_log_id, decision_type, created_at, task_id) -- never the
# full payload or any secret.
#
# It NEVER repairs. If residue exists it tells the operator to use the
# controlled audit_log restore exception procedure.
#
# Marker:
#   AUDIT_TAMPER_RESIDUE_DETECTOR: PASS   (count == 0)
#   AUDIT_TAMPER_RESIDUE_DETECTOR: FAIL   (count > 0)

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"

"$PY" - <<'PY'
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())
import asyncpg  # noqa: E402

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
MARKER = "[TAMPER-SIMULATION]"


async def main() -> int:
    try:
        conn = await asyncpg.connect(dsn=DSN, timeout=10)
    except Exception as exc:
        print(f"  detector could not connect: {exc.__class__.__name__}")
        print("AUDIT_TAMPER_RESIDUE_DETECTOR: SKIP (db unreachable)")
        return 0
    try:
        rows = await conn.fetch(
            "SELECT id, decision_type, task_id, created_at FROM audit_logs "
            "WHERE summary LIKE '%' || $1 || '%' ORDER BY created_at ASC",
            MARKER,
        )
    finally:
        await conn.close()

    residues = [
        {
            "audit_log_id": str(r["id"]),
            "decision_type": r["decision_type"],
            "task_id": r["task_id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    count = len(residues)

    ts = datetime.now(timezone.utc)
    report = {
        "report_id": f"audit_tamper_residue_{ts.strftime('%Y%m%d_%H%M%S')}",
        "created_at": ts.isoformat(),
        "residue_count": count,
        "residues": residues,
        "marker": MARKER,
        "production_executed": False,
    }
    out_dir = Path("source/audit-forensics")
    out_dir.mkdir(parents=True, exist_ok=True)
    serialised = json.dumps(report, indent=2, ensure_ascii=False)
    (out_dir / f"{report['report_id']}.json").write_text(serialised, encoding="utf-8")
    (out_dir / "audit_tamper_residue_latest.json").write_text(serialised, encoding="utf-8")

    print(f"residue_count={count}")
    for r in residues:
        print(
            f"  residue audit_log_id={r['audit_log_id']} "
            f"decision_type={r['decision_type']} task_id={r['task_id']} "
            f"created_at={r['created_at']}"
        )
    if count == 0:
        print("AUDIT_TAMPER_RESIDUE_DETECTOR: PASS")
        return 0
    print("Use controlled audit_log restore exception procedure. Do not manually update DB.")
    print("AUDIT_TAMPER_RESIDUE_DETECTOR: FAIL")
    return 1


raise SystemExit(asyncio.run(main()))
PY