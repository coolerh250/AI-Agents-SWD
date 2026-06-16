"""Stage 51 -- asyncpg store for the backup / DR readiness tables."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from shared.sdk.backup_dr.models import (
    BackupEncryptionConfig,
    BackupManifest,
    BackupOffhostTarget,
    BackupReadinessEvaluation,
    BackupRetentionPolicy,
    BackupRun,
    BackupScheduleDefinition,
    MigrationRollbackCatalogEntry,
    OffhostTransferRun,
    RestoreDrillRun,
)
from shared.sdk.observability.tracing import start_span

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


def _dec(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return fallback
    return value


class BackupDrStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    # ------------------------------------------------------------------ writes
    async def upsert_encryption_config(self, cfg: BackupEncryptionConfig) -> str:
        with start_span(
            "backup_dr.upsert_encryption_config", **{"db.table": "backup_encryption_configs"}
        ):
            conn = await self._connect()
            try:
                row = await conn.fetchrow(
                    "INSERT INTO backup_encryption_configs "
                    "(config_key, key_source, key_ref, key_id, algorithm, status, "
                    " production_usable, test_only, metadata) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb) "
                    "ON CONFLICT (config_key) DO UPDATE SET "
                    " key_source=EXCLUDED.key_source, key_ref=EXCLUDED.key_ref, "
                    " key_id=EXCLUDED.key_id, algorithm=EXCLUDED.algorithm, "
                    " status=EXCLUDED.status, production_usable=EXCLUDED.production_usable, "
                    " test_only=EXCLUDED.test_only, metadata=EXCLUDED.metadata, "
                    " updated_at=now() RETURNING id",
                    cfg.config_key,
                    cfg.key_source,
                    cfg.key_ref,
                    cfg.key_id,
                    cfg.algorithm,
                    cfg.status,
                    cfg.production_usable,
                    cfg.test_only,
                    json.dumps(cfg.metadata or {}),
                )
            finally:
                await conn.close()
            return str(row["id"])

    async def create_backup_run(self, run: BackupRun) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO backup_runs "
                "(backup_key, environment, source_database, status, encrypted, "
                " encryption_config_id, artifact_path, manifest_path, checksum_sha256, "
                " encrypted_checksum_sha256, size_bytes, completed_at, production_executed, "
                " metadata) "
                "VALUES ($1,$2,$3,$4,$5,$6::uuid,$7,$8,$9,$10,$11, now(),$12,$13::jsonb) "
                "ON CONFLICT (backup_key) DO UPDATE SET status=EXCLUDED.status, "
                " encrypted=EXCLUDED.encrypted, checksum_sha256=EXCLUDED.checksum_sha256, "
                " encrypted_checksum_sha256=EXCLUDED.encrypted_checksum_sha256, "
                " completed_at=now() RETURNING id",
                run.backup_key,
                run.environment,
                run.source_database,
                run.status,
                run.encrypted,
                run.encryption_config_id,
                run.artifact_path,
                run.manifest_path,
                run.checksum_sha256,
                run.encrypted_checksum_sha256,
                run.size_bytes,
                run.production_executed,
                json.dumps(run.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_manifest(self, backup_run_id: str, m: BackupManifest) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO backup_manifests "
                "(backup_run_id, manifest_version, source_database, schema_migration_count, "
                " table_count, row_count_summary, artifact_checksum_sha256, "
                " encrypted_artifact_checksum_sha256, encryption_key_id, encryption_algorithm, "
                " manifest_json) "
                "VALUES ($1::uuid,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,$11::jsonb) RETURNING id",
                backup_run_id,
                m.manifest_version,
                m.source_database,
                m.schema_migration_count,
                m.table_count,
                json.dumps(m.row_count_summary or {}),
                m.artifact_checksum_sha256,
                m.encrypted_artifact_checksum_sha256,
                m.encryption_key_id,
                m.encryption_algorithm,
                json.dumps(m.manifest_json or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def upsert_offhost_target(self, t: BackupOffhostTarget) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO backup_offhost_targets "
                "(target_key, target_type, target_uri, status, real_cloud_write_enabled, "
                " test_only, metadata) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb) "
                "ON CONFLICT (target_key) DO UPDATE SET target_type=EXCLUDED.target_type, "
                " target_uri=EXCLUDED.target_uri, status=EXCLUDED.status, "
                " real_cloud_write_enabled=EXCLUDED.real_cloud_write_enabled, "
                " metadata=EXCLUDED.metadata RETURNING id",
                t.target_key,
                t.target_type,
                t.target_uri,
                t.status,
                t.real_cloud_write_enabled,
                t.test_only,
                json.dumps(t.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_transfer_run(
        self, backup_run_id: str | None, target_id: str | None, tr: OffhostTransferRun
    ) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO backup_offhost_transfer_runs "
                "(backup_run_id, target_id, status, source_path, target_path, "
                " source_checksum_sha256, target_checksum_sha256, readback_verified, "
                " real_cloud_write_performed, completed_at, metadata) "
                "VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,$9, now(),$10::jsonb) RETURNING id",
                backup_run_id,
                target_id,
                tr.status,
                tr.source_path,
                tr.target_path,
                tr.source_checksum_sha256,
                tr.target_checksum_sha256,
                tr.readback_verified,
                tr.real_cloud_write_performed,
                json.dumps(tr.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_restore_drill(self, backup_run_id: str | None, d: RestoreDrillRun) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO restore_drill_runs "
                "(backup_run_id, restore_key, target_database, restore_mode, status, "
                " rto_seconds, row_count_verified, schema_verified, application_smoke_verified, "
                " production_restore_performed, completed_at, report_json, metadata) "
                "VALUES ($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9,$10, now(),$11::jsonb,$12::jsonb) "
                "ON CONFLICT (restore_key) DO UPDATE SET status=EXCLUDED.status, "
                " rto_seconds=EXCLUDED.rto_seconds, schema_verified=EXCLUDED.schema_verified, "
                " row_count_verified=EXCLUDED.row_count_verified, completed_at=now() RETURNING id",
                backup_run_id,
                d.restore_key,
                d.target_database,
                d.restore_mode,
                d.status,
                d.rto_seconds,
                d.row_count_verified,
                d.schema_verified,
                d.application_smoke_verified,
                d.production_restore_performed,
                json.dumps(d.report_json or {}),
                json.dumps(d.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def upsert_schedule(self, s: BackupScheduleDefinition) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO backup_schedule_definitions "
                "(schedule_key, schedule_type, schedule_expression, command_preview, enabled, "
                " dry_run_validated, production_schedule_enabled, metadata) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) "
                "ON CONFLICT (schedule_key) DO UPDATE SET schedule_type=EXCLUDED.schedule_type, "
                " schedule_expression=EXCLUDED.schedule_expression, "
                " command_preview=EXCLUDED.command_preview, "
                " dry_run_validated=EXCLUDED.dry_run_validated, metadata=EXCLUDED.metadata "
                "RETURNING id",
                s.schedule_key,
                s.schedule_type,
                s.schedule_expression,
                s.command_preview,
                s.enabled,
                s.dry_run_validated,
                s.production_schedule_enabled,
                json.dumps(s.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def upsert_retention_policy(self, p: BackupRetentionPolicy) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO backup_retention_policies "
                "(policy_key, keep_last, keep_daily, keep_weekly, keep_monthly, delete_enabled, "
                " dry_run_only, metadata) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) "
                "ON CONFLICT (policy_key) DO UPDATE SET keep_last=EXCLUDED.keep_last, "
                " delete_enabled=EXCLUDED.delete_enabled, dry_run_only=EXCLUDED.dry_run_only "
                "RETURNING id",
                p.policy_key,
                p.keep_last,
                p.keep_daily,
                p.keep_weekly,
                p.keep_monthly,
                p.delete_enabled,
                p.dry_run_only,
                json.dumps(p.metadata or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def create_retention_dry_run(self, policy_id: str | None, report: dict) -> str:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO backup_retention_dry_runs "
                "(policy_id, status, candidate_delete_count, actual_delete_count, dry_run_only, "
                " report_json) VALUES ($1::uuid,$2,$3,$4,$5,$6::jsonb) RETURNING id",
                policy_id,
                report.get("status", "completed"),
                int(report.get("candidate_delete_count", 0)),
                int(report.get("actual_delete_count", 0)),
                bool(report.get("dry_run_only", True)),
                json.dumps(report or {}),
            )
        finally:
            await conn.close()
        return str(row["id"])

    async def replace_migration_catalog(self, entries: list[MigrationRollbackCatalogEntry]) -> int:
        conn = await self._connect()
        try:
            async with conn.transaction():
                for e in entries:
                    await conn.execute(
                        "INSERT INTO migration_rollback_catalog "
                        "(migration_file, migration_number, reversibility, down_script_available, "
                        " rollback_notes, risk_level, verified, metadata) "
                        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) "
                        "ON CONFLICT (migration_file) DO UPDATE SET "
                        " migration_number=EXCLUDED.migration_number, "
                        " reversibility=EXCLUDED.reversibility, "
                        " down_script_available=EXCLUDED.down_script_available, "
                        " rollback_notes=EXCLUDED.rollback_notes, risk_level=EXCLUDED.risk_level, "
                        " verified=EXCLUDED.verified, metadata=EXCLUDED.metadata",
                        e.migration_file,
                        e.migration_number,
                        e.reversibility,
                        e.down_script_available,
                        e.rollback_notes,
                        e.risk_level,
                        e.verified,
                        json.dumps(e.metadata or {}),
                    )
        finally:
            await conn.close()
        return len(entries)

    async def create_readiness_evaluation(
        self, ev: BackupReadinessEvaluation, *, report: dict | None = None
    ) -> str:
        conn = await self._connect()
        try:
            metadata = dict(ev.metadata or {})
            if report is not None:
                metadata["report"] = report
            row = await conn.fetchrow(
                "INSERT INTO backup_readiness_evaluations "
                "(evaluation_key, status, encryption_gap_closed, offhost_gap_closed, "
                " schedule_gap_closed, migration_down_gap_closed, remaining_gaps, limitations, "
                " metadata) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb) "
                "ON CONFLICT (evaluation_key) DO UPDATE SET status=EXCLUDED.status, "
                " encryption_gap_closed=EXCLUDED.encryption_gap_closed, "
                " offhost_gap_closed=EXCLUDED.offhost_gap_closed, "
                " schedule_gap_closed=EXCLUDED.schedule_gap_closed, "
                " migration_down_gap_closed=EXCLUDED.migration_down_gap_closed, "
                " remaining_gaps=EXCLUDED.remaining_gaps, limitations=EXCLUDED.limitations, "
                " metadata=EXCLUDED.metadata, evaluated_at=now() RETURNING id",
                ev.evaluation_key,
                ev.status,
                ev.encryption_gap_closed,
                ev.offhost_gap_closed,
                ev.schedule_gap_closed,
                ev.migration_down_gap_closed,
                json.dumps(list(ev.remaining_gaps)),
                json.dumps(list(ev.limitations)),
                json.dumps(metadata),
            )
        finally:
            await conn.close()
        return str(row["id"])

    # ------------------------------------------------------------------- reads
    async def get_latest_encryption_config(self) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT config_key, key_source, key_id, algorithm, status, production_usable, "
                " test_only, updated_at FROM backup_encryption_configs "
                "ORDER BY updated_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "config_key": row["config_key"],
            "key_source": row["key_source"],
            "key_id": row["key_id"],
            "algorithm": row["algorithm"],
            "status": row["status"],
            "production_usable": row["production_usable"],
            "test_only": row["test_only"],
            "raw_key_persisted": False,
            "updated_at": _iso(row["updated_at"]),
        }

    async def get_latest_backup_run(self) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT backup_key, environment, source_database, status, encrypted, "
                " checksum_sha256, encrypted_checksum_sha256, size_bytes, completed_at, "
                " production_executed FROM backup_runs ORDER BY started_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "backup_key": row["backup_key"],
            "environment": row["environment"],
            "source_database": row["source_database"],
            "status": row["status"],
            "encrypted": row["encrypted"],
            "checksum_sha256": row["checksum_sha256"],
            "encrypted_checksum_sha256": row["encrypted_checksum_sha256"],
            "size_bytes": row["size_bytes"],
            "completed_at": _iso(row["completed_at"]),
            "production_executed": row["production_executed"],
        }

    async def get_latest_manifest(self) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT manifest_version, source_database, schema_migration_count, table_count, "
                " encryption_key_id, encryption_algorithm, manifest_json, created_at "
                "FROM backup_manifests ORDER BY created_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "manifest_version": row["manifest_version"],
            "source_database": row["source_database"],
            "schema_migration_count": row["schema_migration_count"],
            "table_count": row["table_count"],
            "encryption_key_id": row["encryption_key_id"],
            "encryption_algorithm": row["encryption_algorithm"],
            "manifest_json": _dec(row["manifest_json"], {}),
            "created_at": _iso(row["created_at"]),
        }

    async def get_latest_transfer(self) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT status, target_path, source_checksum_sha256, target_checksum_sha256, "
                " readback_verified, real_cloud_write_performed, completed_at "
                "FROM backup_offhost_transfer_runs ORDER BY started_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "status": row["status"],
            "target_path": row["target_path"],
            "source_checksum_sha256": row["source_checksum_sha256"],
            "target_checksum_sha256": row["target_checksum_sha256"],
            "readback_verified": row["readback_verified"],
            "real_cloud_write_performed": row["real_cloud_write_performed"],
            "completed_at": _iso(row["completed_at"]),
        }

    async def get_latest_restore_drill(self) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT restore_key, target_database, restore_mode, status, rto_seconds, "
                " row_count_verified, schema_verified, application_smoke_verified, "
                " production_restore_performed, completed_at "
                "FROM restore_drill_runs ORDER BY started_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "restore_key": row["restore_key"],
            "target_database": row["target_database"],
            "restore_mode": row["restore_mode"],
            "status": row["status"],
            "rto_seconds": float(row["rto_seconds"]) if row["rto_seconds"] is not None else None,
            "row_count_verified": row["row_count_verified"],
            "schema_verified": row["schema_verified"],
            "application_smoke_verified": row["application_smoke_verified"],
            "production_restore_performed": row["production_restore_performed"],
            "completed_at": _iso(row["completed_at"]),
        }

    async def get_latest_schedule(self) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT schedule_key, schedule_type, schedule_expression, command_preview, "
                " enabled, dry_run_validated, production_schedule_enabled "
                "FROM backup_schedule_definitions ORDER BY created_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "schedule_key": row["schedule_key"],
            "schedule_type": row["schedule_type"],
            "schedule_expression": row["schedule_expression"],
            "command_preview": row["command_preview"],
            "enabled": row["enabled"],
            "dry_run_validated": row["dry_run_validated"],
            "production_schedule_enabled": row["production_schedule_enabled"],
        }

    async def get_latest_retention(self) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT p.policy_key, p.delete_enabled, p.dry_run_only, d.candidate_delete_count, "
                " d.actual_delete_count, d.status, d.created_at "
                "FROM backup_retention_policies p "
                "LEFT JOIN backup_retention_dry_runs d ON d.policy_id = p.id "
                "ORDER BY d.created_at DESC NULLS LAST, p.created_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "policy_key": row["policy_key"],
            "delete_enabled": row["delete_enabled"],
            "dry_run_only": row["dry_run_only"],
            "candidate_delete_count": row["candidate_delete_count"],
            "actual_delete_count": row["actual_delete_count"],
            "status": row["status"],
            "created_at": _iso(row["created_at"]),
        }

    async def get_migration_catalog(self) -> list[dict]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT migration_file, migration_number, reversibility, down_script_available, "
                " rollback_notes, risk_level, verified FROM migration_rollback_catalog "
                "ORDER BY migration_number NULLS LAST, migration_file"
            )
        finally:
            await conn.close()
        return [
            {
                "migration_file": r["migration_file"],
                "migration_number": r["migration_number"],
                "reversibility": r["reversibility"],
                "down_script_available": r["down_script_available"],
                "rollback_notes": r["rollback_notes"],
                "risk_level": r["risk_level"],
                "verified": r["verified"],
            }
            for r in rows
        ]

    async def get_latest_readiness(self) -> dict | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "SELECT evaluation_key, status, encryption_gap_closed, offhost_gap_closed, "
                " schedule_gap_closed, migration_down_gap_closed, remaining_gaps, limitations, "
                " metadata, evaluated_at FROM backup_readiness_evaluations "
                "ORDER BY evaluated_at DESC LIMIT 1"
            )
        finally:
            await conn.close()
        if not row:
            return None
        return {
            "evaluation_key": row["evaluation_key"],
            "status": row["status"],
            "encryption_gap_closed": row["encryption_gap_closed"],
            "offhost_gap_closed": row["offhost_gap_closed"],
            "schedule_gap_closed": row["schedule_gap_closed"],
            "migration_down_gap_closed": row["migration_down_gap_closed"],
            "remaining_gaps": _dec(row["remaining_gaps"], []),
            "limitations": _dec(row["limitations"], []),
            "metadata": _dec(row["metadata"], {}),
            "evaluated_at": _iso(row["evaluated_at"]),
        }

    async def get_latest_report(self) -> dict | None:
        latest = await self.get_latest_readiness()
        if not latest:
            return None
        report = (latest.get("metadata") or {}).get("report")
        return report if isinstance(report, dict) else None


__all__ = ["BackupDrStore", "DEFAULT_DATABASE_URL"]
