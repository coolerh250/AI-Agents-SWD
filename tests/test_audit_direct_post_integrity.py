"""Stage 39 -- audit-service direct POST integrity closure (structural)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_audit_service_main() -> str:
    return (_REPO_ROOT / "apps" / "audit-service" / "src" / "main.py").read_text(encoding="utf-8")


def test_direct_post_handler_uses_shared_integrity_writer():
    src = _read_audit_service_main()
    assert "from shared.sdk.audit_integrity import" in src
    assert "create_integrity_record_in_txn" in src


def test_direct_post_handler_wraps_inserts_in_txn():
    src = _read_audit_service_main()
    # The handler must open a transaction and call BOTH the audit_logs
    # INSERT and the integrity writer inside it.
    assert "async with conn.transaction()" in src
    assert "INSERT INTO audit_logs" in src
    assert "create_integrity_record_in_txn" in src


def test_direct_post_handler_returns_503_on_integrity_failure():
    src = _read_audit_service_main()
    assert "status_code=503" in src
    assert "transaction" in src.lower()


def test_direct_post_handler_records_integrity_metrics():
    src = _read_audit_service_main()
    assert "AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL" in src
    assert "AUDIT_DIRECT_POST_INTEGRITY_FAILURES_TOTAL" in src


def test_direct_post_handler_never_reads_key_value():
    src = _read_audit_service_main()
    # The audit-service must not log/read raw AUDIT_HMAC_KEY value at
    # the request boundary; only the keyring loader (inside the SDK)
    # may touch it, and only at process start.
    for forbidden in (
        'os.environ.get("AUDIT_HMAC_KEY")',
        "os.environ['AUDIT_HMAC_KEY']",
    ):
        assert forbidden not in src, f"audit-service must not read {forbidden} directly"


def test_audit_service_exposes_keyring_status_endpoint():
    src = _read_audit_service_main()
    assert '@app.get("/audit/keyring/status")' in src


def test_audit_event_in_model_has_expected_fields():
    src = _read_audit_service_main()
    for field in ("task_id", "agent", "decision_type", "summary", "result", "artifact_refs"):
        assert field in src
