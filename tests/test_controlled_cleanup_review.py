"""Step 61 -- controlled cleanup review."""

from __future__ import annotations

import pytest

from shared.sdk.backup_restore_dr import (
    CleanupReviewError,
    build_cleanup_review,
    classify_candidate,
    is_path_allowlisted,
)


def test_arbitrary_path_rejected() -> None:
    assert is_path_allowlisted("/etc/passwd") is False
    assert is_path_allowlisted("../secrets") is False
    assert is_path_allowlisted(".runtime/backup-dr/x.json") is True


@pytest.mark.parametrize(
    "cls", ["database_dump", "redis_snapshot", "audit_export", "cluster_runtime_state"]
)
def test_blocked_classifications(cls: str) -> None:
    row = classify_candidate(".runtime/backup-dr/x", cls)
    assert row["decision"] == "blocked"


def test_temporary_trace_allowed() -> None:
    row = classify_candidate(".runtime/tracing/a.trace", "temporary_trace")
    assert row["decision"] == "allowed"


@pytest.mark.parametrize("scope", ["kind_cluster", "argocd", "active_database", "active_redis"])
def test_forbidden_scope_raises(scope: str) -> None:
    with pytest.raises(CleanupReviewError):
        build_cleanup_review(scope=scope, candidates=[])


def test_review_never_executes() -> None:
    review = build_cleanup_review(
        scope="runtime_artifacts",
        candidates=[
            {"path": ".runtime/tracing/a", "classification": "temporary_trace", "size_bytes": 1},
            {
                "path": ".runtime/backup-dr/d.sql",
                "classification": "database_dump",
                "size_bytes": 2,
            },
        ],
    )
    d = review.to_dict()
    assert d["cleanup_executed"] is False
    assert d["allowed_count"] == 1
    assert d["blocked_count"] == 1
