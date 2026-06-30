"""Step 61 -- backup artifact classification."""

from __future__ import annotations

from shared.sdk.backup_restore_dr import commit_allowed, load_classes
from shared.sdk.backup_restore_dr.models import ARTIFACT_CLASSES


def test_all_classes_present() -> None:
    classes = load_classes()
    for name in ARTIFACT_CLASSES:
        assert name in classes, name


def test_dumps_never_committed() -> None:
    assert commit_allowed("database_dump") is False
    assert commit_allowed("redis_snapshot") is False


def test_temporary_cleanup_allowed_without_approval() -> None:
    classes = load_classes()
    for name in ("temporary_trace", "temporary_build_cache"):
        assert classes[name]["cleanup_allowed"] is True
        assert classes[name]["cleanup_requires_approval"] is False


def test_cluster_and_scheduled_not_auto_cleaned() -> None:
    classes = load_classes()
    assert classes["cluster_runtime_state"]["cleanup_allowed"] is False
    assert classes["scheduled_dr_report"]["cleanup_allowed"] is False
