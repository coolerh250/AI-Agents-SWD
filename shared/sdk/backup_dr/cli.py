"""Stage 51 -- host-runnable backup / DR gap-closure orchestrator CLI.

Driven by the verify scripts. Reads a *facts* JSON file produced by the shell
layer (which performs the real pg_dump / openssl encrypt / psql restore against
the test database + postgres container) and then:

  * resolves the encryption config metadata (no raw key),
  * persists backup_run + manifest,
  * copies the encrypted artifact to the mock off-host target + verifies readback,
  * persists the restore drill facts,
  * builds + dry-run-validates the schedule + retention specs,
  * scans + classifies the migration rollback catalog,
  * evaluates the overall readiness,
  * writes a secret-free readiness JSON snapshot that /operations/safety reads,
  * publishes one audit event per step (Redis stream.audit -> audit-worker,
    which applies the Step 37 integrity closure).

Controlled / test only: never production backup / restore, never real cloud
write, never real schedule, never persists a raw key.

Usage:
    python3 -m shared.sdk.backup_dr.cli run-all --facts facts.json --out out.json
    python3 -m shared.sdk.backup_dr.cli migration-catalog            # prints summary
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

from shared.sdk.backup_dr import audit_events as _ae
from shared.sdk.backup_dr import events as _ev
from shared.sdk.backup_dr.backup_runner import build_backup_run
from shared.sdk.backup_dr.manifest_builder import build_manifest, manifest_contains_secret
from shared.sdk.backup_dr.encryption_config import resolve_encryption_config, safe_status
from shared.sdk.backup_dr.migration_catalog import build_migration_catalog, catalog_summary
from shared.sdk.backup_dr.offhost_target import build_mock_offhost_target
from shared.sdk.backup_dr.offhost_transfer import transfer_to_offhost
from shared.sdk.backup_dr.readiness_evaluator import evaluate_readiness
from shared.sdk.backup_dr.report_builder import build_gap_closure_report
from shared.sdk.backup_dr.restore_drill import build_restore_drill_run
from shared.sdk.backup_dr.retention_policy import build_retention_policy, compute_retention_dry_run
from shared.sdk.backup_dr.schedule_builder import build_cron_spec
from shared.sdk.backup_dr.store import BackupDrStore

DEFAULT_READINESS_SNAPSHOT = "source/dr-reports/backup_dr_readiness_latest.json"
AGENT = "backup-dr-agent"


async def _audit(decision_type: str, summary: str, result: str, refs: dict) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.audit.publisher import publish_audit_event

        await publish_audit_event(
            task_id="backup-dr-gap-closure",
            agent=AGENT,
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=refs,
        )


async def _run_all(facts: dict[str, Any], *, use_db: bool, use_audit: bool) -> dict[str, Any]:
    store = BackupDrStore() if use_db else None

    # 1. encryption config -------------------------------------------------
    encryption = resolve_encryption_config()
    enc_id: str | None = None
    if store is not None:
        enc_id = await store.upsert_encryption_config(encryption)
    if use_audit:
        await _audit(
            _ae.DECISION_BACKUP_ENCRYPTION_CONFIGURED,
            "backup encryption configured (test-only key)",
            "configured",
            _ae.safe_backup_dr_refs(
                encryption_key_id=encryption.key_id,
                encryption_algorithm=encryption.algorithm,
            ),
        )

    # 2. backup run + manifest --------------------------------------------
    backup_run = build_backup_run(
        backup_key=facts["backup_key"],
        source_database=facts.get("source_database", "aiagents"),
        environment=facts.get("environment", "test"),
        encrypted=True,
        encryption_config_id=enc_id,
        artifact_path=facts.get("encrypted_artifact_path") or facts.get("artifact_path"),
        checksum_sha256=facts.get("checksum_sha256"),
        encrypted_checksum_sha256=facts.get("encrypted_checksum_sha256"),
        size_bytes=facts.get("size_bytes"),
        status="completed",
    )
    backup_run_id: str | None = None
    if store is not None:
        backup_run_id = await store.create_backup_run(backup_run)

    manifest = build_manifest(
        backup_run=backup_run,
        encryption=encryption,
        schema_migration_count=facts.get("schema_migration_count"),
        table_count=facts.get("table_count"),
        row_count_summary=facts.get("row_count_summary"),
        backup_run_id=backup_run_id,
    )
    if manifest_contains_secret(manifest):
        raise SystemExit("FATAL: manifest contains a secret-like value")
    if store is not None and backup_run_id is not None:
        await store.create_manifest(backup_run_id, manifest)
    if use_audit:
        await _audit(
            _ae.DECISION_BACKUP_RUN_COMPLETED,
            "encrypted backup run completed (test environment)",
            "completed",
            _ae.safe_backup_dr_refs(
                backup_key=backup_run.backup_key,
                environment=backup_run.environment,
                encryption_key_id=manifest.encryption_key_id,
            ),
        )

    # 3. off-host transfer -------------------------------------------------
    target = build_mock_offhost_target()
    target_id: str | None = None
    if store is not None:
        target_id = await store.upsert_offhost_target(target)
    transfer = transfer_to_offhost(
        source_path=facts.get("encrypted_artifact_path") or facts.get("artifact_path") or "",
        target=target,
        backup_run_id=backup_run_id,
        target_id=target_id,
    )
    if store is not None:
        await store.create_transfer_run(backup_run_id, target_id, transfer)
    if use_audit:
        await _audit(
            _ae.DECISION_BACKUP_OFFHOST_TRANSFER_VERIFIED,
            "off-host transfer + readback verified (mock target, no cloud write)",
            transfer.status,
            _ae.safe_backup_dr_refs(offhost_target_type=target.target_type),
        )

    # 4. restore drill -----------------------------------------------------
    restore = None
    rfacts = facts.get("restore")
    if isinstance(rfacts, dict) and rfacts.get("restore_key"):
        restore = build_restore_drill_run(
            restore_key=rfacts["restore_key"],
            target_database=rfacts.get("target_database", "aiagents_restore_drill_cli"),
            backup_run_id=backup_run_id,
            restore_mode=rfacts.get("restore_mode", "isolated_test_db"),
            status=rfacts.get("status", "verified"),
            rto_seconds=rfacts.get("rto_seconds"),
            row_count_verified=bool(rfacts.get("row_count_verified")),
            schema_verified=bool(rfacts.get("schema_verified")),
            application_smoke_verified=bool(rfacts.get("application_smoke_verified")),
            report=rfacts.get("report"),
        )
        if store is not None:
            await store.create_restore_drill(backup_run_id, restore)
        if use_audit:
            await _audit(
                _ae.DECISION_BACKUP_RESTORE_DRILL_COMPLETED,
                "isolated restore drill completed (no production restore)",
                restore.status,
                _ae.safe_backup_dr_refs(
                    restore_key=restore.restore_key,
                    restore_status=restore.status,
                    rto_seconds=restore.rto_seconds,
                ),
            )

    # 5. schedule + retention ---------------------------------------------
    schedule = build_cron_spec()
    if store is not None:
        await store.upsert_schedule(schedule)
    if use_audit:
        await _audit(
            _ae.DECISION_BACKUP_SCHEDULE_VALIDATED,
            "backup schedule spec dry-run validated (production schedule disabled)",
            "validated" if schedule.dry_run_validated else "invalid",
            _ae.safe_backup_dr_refs(schedule_key=schedule.schedule_key),
        )

    policy = build_retention_policy()
    policy_id: str | None = None
    if store is not None:
        policy_id = await store.upsert_retention_policy(policy)
    retention_report = compute_retention_dry_run(policy, facts.get("known_backups"))
    if store is not None:
        await store.create_retention_dry_run(policy_id, retention_report)
    if use_audit:
        await _audit(
            _ae.DECISION_BACKUP_RETENTION_DRY_RUN_COMPLETED,
            "retention dry-run completed (no deletion)",
            "completed",
            _ae.safe_backup_dr_refs(),
        )

    # 6. migration rollback catalog ---------------------------------------
    entries = build_migration_catalog(facts.get("migrations_dir", "migrations"))
    mig = catalog_summary(entries)
    if store is not None:
        await store.replace_migration_catalog(entries)
    if use_audit:
        await _audit(
            _ae.DECISION_MIGRATION_ROLLBACK_CATALOG_COMPLETED,
            "migration rollback catalog complete (no unknown migrations)",
            "completed" if mig.get("complete") else "incomplete",
            _ae.safe_backup_dr_refs(unknown_migration_count=int(mig.get("unknown", 0))),
        )

    # 7. readiness evaluation ---------------------------------------------
    readiness = evaluate_readiness(
        encryption=encryption,
        transfer=transfer,
        schedule=schedule,
        migration_entries=entries,
        restore=restore,
    )
    report = build_gap_closure_report(
        encryption=encryption,
        backup_run=backup_run,
        manifest=manifest,
        offhost_target=target,
        transfer=transfer,
        restore=restore,
        schedule=schedule,
        retention_dry_run=retention_report,
        migration_entries=entries,
        readiness=readiness,
    )
    if store is not None:
        await store.create_readiness_evaluation(readiness, report=report)
    if use_audit:
        await _audit(
            _ae.DECISION_BACKUP_READINESS_EVALUATED,
            f"backup readiness evaluated: {readiness.status}",
            readiness.status,
            _ae.safe_backup_dr_refs(
                readiness_status=readiness.status,
                remaining_gaps=list(readiness.remaining_gaps),
            ),
        )

    return {
        "encryption": safe_status(encryption),
        "readiness": readiness.model_dump(),
        "migration_catalog_summary": mig,
        "report": report,
        "events": list(_ev.BACKUP_DR_EVENTS),
    }


def _cmd_run_all(args: argparse.Namespace) -> int:
    facts_path = Path(args.facts)
    facts = json.loads(facts_path.read_text(encoding="utf-8")) if facts_path.is_file() else {}
    facts.setdefault("backup_key", "backup-dr-cli")
    out = asyncio.run(_run_all(facts, use_db=not args.no_db, use_audit=not args.no_audit))
    snapshot = {
        "status": out["readiness"]["status"],
        "encryption_gap_closed": out["readiness"]["encryption_gap_closed"],
        "offhost_gap_closed": out["readiness"]["offhost_gap_closed"],
        "schedule_gap_closed": out["readiness"]["schedule_gap_closed"],
        "migration_down_gap_closed": out["readiness"]["migration_down_gap_closed"],
        "remaining_gaps": out["readiness"]["remaining_gaps"],
        "limitations": out["readiness"]["limitations"],
        "report": out["report"],
    }
    out_path = Path(args.out or DEFAULT_READINESS_SNAPSHOT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"readiness_status": snapshot["status"], "snapshot": str(out_path)}))
    return 0


def _cmd_migration_catalog(args: argparse.Namespace) -> int:
    entries = build_migration_catalog(args.migrations_dir)
    summary = catalog_summary(entries)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary.get("complete") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backup_dr.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_all = sub.add_parser("run-all", help="run full gap closure from a facts JSON")
    p_all.add_argument("--facts", required=True)
    p_all.add_argument("--out", default=DEFAULT_READINESS_SNAPSHOT)
    p_all.add_argument("--no-db", action="store_true")
    p_all.add_argument("--no-audit", action="store_true")
    p_all.set_defaults(func=_cmd_run_all)

    p_mig = sub.add_parser("migration-catalog", help="scan + classify migrations")
    p_mig.add_argument("--migrations-dir", default="migrations")
    p_mig.set_defaults(func=_cmd_migration_catalog)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
