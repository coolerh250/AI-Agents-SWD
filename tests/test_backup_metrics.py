"""Stage 36 -- backup / restore / DR Prometheus metrics registered."""

from __future__ import annotations


def test_backup_metrics_registered():
    from shared.sdk.observability import metrics

    for name in (
        "BACKUP_CREATED_TOTAL",
        "BACKUP_ENCRYPTED_TOTAL",
        "BACKUP_UPLOAD_SKIPPED_TOTAL",
        "BACKUP_UPLOAD_SUCCESS_TOTAL",
        "RESTORE_DRILL_RUNS_TOTAL",
        "RESTORE_DRILL_FAILED_TOTAL",
        "BACKUP_DURATION_SECONDS",
        "RESTORE_DURATION_SECONDS",
        "BACKUP_ARTIFACT_SIZE_BYTES",
        "BACKUP_RTO_SECONDS",
        "BACKUP_RPO_SECONDS",
    ):
        assert hasattr(metrics, name), f"missing metric: {name}"


def test_backup_metrics_can_be_incremented():
    from shared.sdk.observability import metrics

    metrics.BACKUP_CREATED_TOTAL.labels(
        environment="local", storage_mode="local-filesystem", encrypted="true"
    ).inc()
    metrics.BACKUP_ENCRYPTED_TOTAL.labels(mode="openssl-aes-256-cbc").inc()
    metrics.BACKUP_UPLOAD_SKIPPED_TOTAL.labels(
        mode="s3-compatible-placeholder", reason="s3_upload_not_implemented"
    ).inc()
    metrics.BACKUP_UPLOAD_SUCCESS_TOTAL.labels(mode="local-filesystem").inc()
    metrics.RESTORE_DRILL_RUNS_TOTAL.labels(status="passed").inc()
    metrics.RESTORE_DRILL_FAILED_TOTAL.labels(reason="pg_restore_rc=1").inc()
    metrics.BACKUP_DURATION_SECONDS.observe(1.5)
    metrics.RESTORE_DURATION_SECONDS.observe(3.0)
    metrics.BACKUP_ARTIFACT_SIZE_BYTES.observe(1024 * 1024)
    metrics.BACKUP_RTO_SECONDS.observe(10)
    metrics.BACKUP_RPO_SECONDS.observe(900)


def test_backup_metrics_have_expected_labels():
    from shared.sdk.observability import metrics

    # Counter._labelnames is the public-ish accessor on prom Counter.
    assert metrics.BACKUP_CREATED_TOTAL._labelnames == (
        "environment",
        "storage_mode",
        "encrypted",
    )
    assert metrics.BACKUP_UPLOAD_SKIPPED_TOTAL._labelnames == ("mode", "reason")
    assert metrics.RESTORE_DRILL_RUNS_TOTAL._labelnames == ("status",)
