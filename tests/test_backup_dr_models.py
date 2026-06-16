"""Stage 51 -- Backup / DR Pydantic model invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.backup_dr.models import (
    BackupEncryptionConfig,
    BackupReadinessEvaluation,
    BackupRun,
    RestoreDrillRun,
)


def test_defaults_are_controlled() -> None:
    run = BackupRun(backup_key="k", source_database="aiagents")
    assert run.environment == "test"
    assert run.production_executed is False
    assert run.encrypted is False


def test_encryption_config_no_raw_key_field() -> None:
    cfg = BackupEncryptionConfig(config_key="c")
    dumped = cfg.model_dump()
    for forbidden in ("key", "raw_key", "secret", "password", "token"):
        assert forbidden not in dumped


def test_restore_drill_production_flag_default_false() -> None:
    d = RestoreDrillRun(restore_key="r", target_database="aiagents_restore_drill_x")
    assert d.production_restore_performed is False


def test_readiness_eval_defaults() -> None:
    ev = BackupReadinessEvaluation(evaluation_key="e")
    assert ev.status == "passed_with_gaps"
    assert ev.remaining_gaps == []


def test_strict_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        BackupRun(backup_key="k", source_database="db", bogus_field=1)  # type: ignore[call-arg]
