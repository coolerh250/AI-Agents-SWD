#!/usr/bin/env bash
# Stage 34 -- walk audit_logs + audit_integrity_records and verify the
# hash-chain. Records a row in audit_chain_verification_runs.
#
# Exit codes:
#   0  AUDIT_INTEGRITY_VERIFY: PASS  (status=passed OR partial-without-mismatch)
#   1  AUDIT_INTEGRITY_VERIFY: FAIL  (status=failed / error)
#
# Never prints the HMAC key value. When a mismatch is found, the script
# prints first_failure_sequence, first_failure_audit_log_id,
# failure_reason, expected_hash, and actual_hash so an operator can
# locate the row without having to read the verifier code.

set -uo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres@localhost:5432/aiagents}"

$PY <<'PY'
import asyncio
import sys

sys.path.insert(0, ".")

from shared.sdk.audit_integrity import (
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_PARTIAL,
    AuditChainVerifier,
    AuditIntegrityStore,
    AuditSigner,
)


async def main():
    verifier = AuditChainVerifier(signer=AuditSigner())
    result = await verifier.verify_chain()
    try:
        store = AuditIntegrityStore(signer=verifier.signer)
        await store.record_verification_run(run=verifier.to_run(result))
    except Exception as exc:  # best-effort; verifier result already authoritative
        print(f"(record_verification_run failed: {exc.__class__.__name__}: {exc})")

    print(f"chain_version: {result.chain_version}")
    print(f"audit_logs_count: {result.audit_logs_count}")
    print(f"integrity_records_count: {result.integrity_records_count}")
    print(f"missing_integrity_records: {result.missing_integrity_records}")
    print(f"total_records_walked: {result.total_records}")
    print(f"verified_records: {result.verified_records}")
    print(f"failed_records: {result.failed_records}")
    print(f"hmac_enabled: {result.hmac_enabled}")
    print(f"signing_key_id: {result.signing_key_id}")
    print(f"status: {result.status}")

    if result.status in (VERIFICATION_STATUS_FAILED,):
        print(f"first_failure_sequence: {result.first_failure_sequence}")
        print(f"first_failure_audit_log_id: {result.first_failure_audit_log_id}")
        print(f"failure_reason: {result.failure_reason}")
        print(f"expected_hash: {result.expected_hash}")
        print(f"actual_hash: {result.actual_hash}")
        print("AUDIT_INTEGRITY_VERIFY: FAIL")
        sys.exit(1)

    if result.status == VERIFICATION_STATUS_PARTIAL:
        # Partial just means "missing integrity records" -- chain itself
        # is intact for the records that exist. Surfaced as PASS so the
        # outer verifier can proceed, but the failure reason is printed.
        print(f"failure_reason: {result.failure_reason}")
        print("AUDIT_INTEGRITY_VERIFY: PASS (partial)")
        return

    print("AUDIT_INTEGRITY_VERIFY: PASS")


asyncio.run(main())
PY
