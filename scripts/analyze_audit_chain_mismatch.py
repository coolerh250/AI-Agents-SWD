#!/usr/bin/env python3
"""Stage 42 -- audit chain forensic analyzer.

READ-ONLY. Scans the full integrity chain, recomputes hashes, classifies the
root cause, and writes a redacted JSON forensic report. Never mutates the DB.
Never emits a secret / token / key value.

Usage:
    python scripts/analyze_audit_chain_mismatch.py [--output-dir DIR] [--quiet]

Writes:
    source/audit-forensics/audit_forensic_{timestamp}.json
    source/audit-forensics/audit_forensic_latest.json

Exit code is always 0 when the analysis completes (a degraded chain is a
finding, not a tool failure). Exit 2 only on an analysis error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

from shared.sdk.audit_integrity.forensics import (  # noqa: E402
    AuditChainForensicAnalyzer,
    classify_chain_root_cause,
)
from shared.sdk.audit_integrity.models import CHAIN_VERSION  # noqa: E402

DEFAULT_OUTPUT_DIR = "source/audit-forensics"


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _database_name(dsn: str) -> str:
    # postgresql://user@host:port/dbname -> dbname (no creds echoed)
    tail = dsn.rsplit("/", 1)[-1]
    return tail.split("?", 1)[0] or "unknown"


def _recommended_action(classification: dict) -> str:
    if not classification.get("root_cause_classification"):
        return "no_action_chain_clean"
    if classification.get("repair_allowed"):
        return "controlled_repair_allowed_pending_operator_approval"
    return "stop_at_forensic_report_no_safe_repair"


async def _run(output_dir: str, quiet: bool) -> int:
    dsn = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
    analyzer = AuditChainForensicAnalyzer(dsn=dsn)
    failed = await analyzer.scan(chain_version=CHAIN_VERSION)
    failed_dicts = [r.to_dict() for r in failed]
    classification = classify_chain_root_cause(failed)

    failed_sequences = [r.sequence_number for r in failed]
    first_failed = failed_sequences[0] if failed_sequences else None
    production_involved = classification.get("production_executed_involved", False)

    cluster_summary: dict[str, int] = {}
    for r in failed:
        cluster_summary[r.suspected_root_cause] = cluster_summary.get(r.suspected_root_cause, 0) + 1

    ts = datetime.now(timezone.utc)
    report = {
        "report_id": f"audit_forensic_{ts.strftime('%Y%m%d_%H%M%S')}",
        "created_at": ts.isoformat(),
        "git_commit": _git_commit(),
        "database": _database_name(dsn),
        "chain_version": CHAIN_VERSION,
        "verifier_mode": "forensic_full_scan",
        "first_failed_sequence": first_failed,
        "failed_sequences": failed_sequences,
        "failed_records_count": len(failed),
        "failed_records": failed_dicts,
        "failure_cluster_summary": cluster_summary,
        "root_cause_classification": classification.get("root_cause_classification"),
        "confidence": classification.get("confidence"),
        "affected_sequence_range": classification.get("affected_sequence_range"),
        "affected_decision_types": classification.get("affected_decision_types"),
        "recommended_action": _recommended_action(classification),
        "repair_allowed": bool(classification.get("repair_allowed")),
        "repair_risk": classification.get("repair_risk"),
        "repair_policy_reason": classification.get("repair_policy_reason"),
        "production_executed": bool(production_involved),
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{report['report_id']}.json"
    latest_path = out_dir / "audit_forensic_latest.json"
    serialised = json.dumps(report, indent=2, ensure_ascii=False)
    report_path.write_text(serialised, encoding="utf-8")
    latest_path.write_text(serialised, encoding="utf-8")

    if not quiet:
        print(f"first_failed_sequence={first_failed}")
        print(f"failed_records_count={len(failed)}")
        print(f"root_cause_classification={report['root_cause_classification']}")
        print(f"repair_allowed={report['repair_allowed']}")
        print(f"repair_risk={report['repair_risk']}")
        print(f"production_executed={report['production_executed']}")
        print(f"report_path={report_path}")
    print("AUDIT_CHAIN_FORENSICS_REPORT: WRITTEN")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit chain forensic analyzer")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args.output_dir, args.quiet))
    except Exception as exc:  # pragma: no cover - defensive
        print(f"AUDIT_CHAIN_FORENSICS_REPORT: ERROR {exc.__class__.__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
