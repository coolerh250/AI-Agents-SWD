"""Stage 51 -- no raw key / secret leaks through SDK outputs or report."""

from __future__ import annotations

import json

from shared.sdk.backup_dr.backup_runner import build_backup_run
from shared.sdk.backup_dr.encryption_config import resolve_encryption_config, safe_status
from shared.sdk.backup_dr.manifest_builder import build_manifest
from shared.sdk.backup_dr.migration_catalog import build_migration_catalog
from shared.sdk.backup_dr.offhost_target import build_mock_offhost_target
from shared.sdk.backup_dr.offhost_transfer import transfer_to_offhost
from shared.sdk.backup_dr.readiness_evaluator import evaluate_readiness
from shared.sdk.backup_dr.report_builder import build_gap_closure_report
from shared.sdk.backup_dr.retention_policy import build_retention_policy, compute_retention_dry_run
from shared.sdk.backup_dr.schedule_builder import build_cron_spec

RAW_KEY = "TOP-SECRET-RAW-KEY-abcdef0123456789"


def test_report_contains_no_raw_key(tmp_path, monkeypatch) -> None:
    keyf = tmp_path / "k"
    keyf.write_text(RAW_KEY, encoding="utf-8")
    monkeypatch.setenv("BACKUP_DR_TEST_KEY_FILE", str(keyf))
    monkeypatch.setenv("BACKUP_DR_OFFHOST_DIR", str(tmp_path / "offhost"))
    art = tmp_path / "b.enc"
    art.write_bytes(b"ENC")

    enc = resolve_encryption_config()
    run = build_backup_run(
        backup_key="b",
        source_database="aiagents",
        encrypted=True,
        checksum_sha256="aa",
        encrypted_checksum_sha256="bb",
    )
    manifest = build_manifest(backup_run=run, encryption=enc)
    target = build_mock_offhost_target()
    transfer = transfer_to_offhost(source_path=str(art), target=target)
    schedule = build_cron_spec()
    entries = build_migration_catalog("migrations")
    policy = build_retention_policy()
    retention = compute_retention_dry_run(policy, [])
    readiness = evaluate_readiness(
        encryption=enc,
        transfer=transfer,
        schedule=schedule,
        migration_entries=entries,
        restore=None,
    )
    report = build_gap_closure_report(
        encryption=enc,
        backup_run=run,
        manifest=manifest,
        offhost_target=target,
        transfer=transfer,
        restore=None,
        schedule=schedule,
        retention_dry_run=retention,
        migration_entries=entries,
        readiness=readiness,
    )
    blob = json.dumps(report)
    assert RAW_KEY not in blob
    assert "password" not in blob.lower()
    assert report["safety_evidence"]["raw_key_persisted"] is False
    assert RAW_KEY not in json.dumps(safe_status(enc))
