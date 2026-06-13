#!/usr/bin/env bash
# Stage 34 -- simulate a tamper, confirm the verifier detects it, and
# restore the row before the script exits so the real audit chain is
# untouched.
#
# The verifier opens its own short-lived connection (the integrity
# tables sit beside audit_logs in Postgres), so a same-transaction
# tamper-then-read pattern would never expose the mutation -- the
# verifier would see the pre-update view from a separate snapshot.
# Instead we COMMIT a one-row mutation, re-run the verifier (which
# now sees the divergent canonical_payload_hash), then UPDATE back to
# the original value in a try/finally so even an exception path
# leaves the row intact.
#
# Outputs AUDIT_TAMPER_DETECTION_SMOKE: PASS when every phase succeeds.

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"

$PY <<'PY'
import asyncio
import os
import sys

import asyncpg

sys.path.insert(0, ".")

from shared.sdk.audit_integrity import (
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_PARTIAL,
    VERIFICATION_STATUS_PASSED,
    AuditChainVerifier,
)

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")


async def main():
    verifier = AuditChainVerifier(dsn=DSN)
    baseline = await verifier.verify_chain()
    if baseline.status not in (VERIFICATION_STATUS_PASSED, VERIFICATION_STATUS_PARTIAL):
        print(
            f"baseline verify failed: status={baseline.status} "
            f"reason={baseline.failure_reason}"
        )
        print("AUDIT_TAMPER_DETECTION_SMOKE: FAIL")
        sys.exit(1)
    print(f"baseline_status: {baseline.status}")

    # Pick a row that has an integrity record. Use the latest one so
    # the test is independent of insertion order and works against
    # any cluster size.
    conn = await asyncpg.connect(dsn=DSN, timeout=5)
    try:
        target = await conn.fetchrow(
            "SELECT al.id, al.summary FROM audit_logs al "
            "JOIN audit_integrity_records r ON r.audit_log_id = al.id "
            "ORDER BY r.sequence_number DESC LIMIT 1"
        )
    finally:
        await conn.close()
    if target is None:
        print("no audit_logs/integrity row available for tamper simulation")
        print("AUDIT_TAMPER_DETECTION_SMOKE: FAIL")
        sys.exit(1)
    audit_log_id = str(target["id"])
    original_summary = target["summary"]
    tampered_summary = (original_summary or "") + " [TAMPER-SIMULATION]"

    result = None
    try:
        # Commit the mutation so the verifier (separate connection)
        # can observe it.
        conn = await asyncpg.connect(dsn=DSN, timeout=5)
        try:
            await conn.execute(
                "UPDATE audit_logs SET summary = $1 WHERE id = $2",
                tampered_summary,
                audit_log_id,
            )
        finally:
            await conn.close()

        result = await verifier.verify_chain()
        print(f"tamper_status: {result.status}")
        print(f"failure_reason: {result.failure_reason}")
        print(f"first_failure_audit_log_id: {result.first_failure_audit_log_id}")
        print(f"first_failure_sequence: {result.first_failure_sequence}")
    finally:
        # Always restore the original row -- even on an exception path
        # so a partial run cannot leave the test cluster with a real
        # tamper sitting in audit_logs.
        restore = await asyncpg.connect(dsn=DSN, timeout=5)
        try:
            await restore.execute(
                "UPDATE audit_logs SET summary = $1 WHERE id = $2",
                original_summary,
                audit_log_id,
            )
        finally:
            await restore.close()

    if result is None:
        print("verifier did not run")
        print("AUDIT_TAMPER_DETECTION_SMOKE: FAIL")
        sys.exit(1)

    # Re-read after restore to confirm no permanent change.
    conn = await asyncpg.connect(dsn=DSN, timeout=5)
    try:
        row = await conn.fetchrow(
            "SELECT summary FROM audit_logs WHERE id = $1", audit_log_id
        )
    finally:
        await conn.close()
    if row is None or row["summary"] != original_summary:
        print("WARN: tamper restore did not return the original row")
        print("AUDIT_TAMPER_DETECTION_SMOKE: FAIL")
        sys.exit(1)

    if result.status != VERIFICATION_STATUS_FAILED or not result.failure_reason:
        print("verifier did NOT detect simulated tamper")
        print("AUDIT_TAMPER_DETECTION_SMOKE: FAIL")
        sys.exit(1)

    expected_reasons = {"canonical_payload_hash_mismatch"}
    if result.failure_reason not in expected_reasons:
        # Other mismatch types are still detection success, but flag them
        # so a reviewer notices an unexpected pathway.
        print(f"(unexpected failure_reason: {result.failure_reason})")

    # Final re-verify must be PASS again now that the mutation is rolled back.
    post = await verifier.verify_chain()
    if post.status not in (VERIFICATION_STATUS_PASSED, VERIFICATION_STATUS_PARTIAL):
        print(f"post-rollback verify regressed: status={post.status}")
        print("AUDIT_TAMPER_DETECTION_SMOKE: FAIL")
        sys.exit(1)
    print(f"post_rollback_status: {post.status}")
    print("AUDIT_TAMPER_DETECTION_SMOKE: PASS")


asyncio.run(main())
PY
