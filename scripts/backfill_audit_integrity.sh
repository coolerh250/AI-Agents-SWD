#!/usr/bin/env bash
# Stage 34 -- backfill audit_integrity_records for existing audit_logs rows.
#
# Idempotent: if every audit_logs row already has an integrity record
# the script exits with AUDIT_INTEGRITY_BACKFILL: PASS and no rows
# are written. Otherwise the integrity records are appended in
# sort-stable order (created_at ASC, id ASC) so the chain remains
# deterministic across re-runs.
#
# The script reads AUDIT_HMAC_KEY from env. When the key is absent
# the integrity records record signature_status=signing_key_not_configured.
# The key value is NEVER printed; the only signing metadata surfaced
# is the opaque signing_key_id.

set -uo pipefail

cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres@localhost:5432/aiagents}"

$PY <<'PY'
import asyncio
import os
import sys

sys.path.insert(0, ".")

from shared.sdk.audit_integrity import AuditIntegrityStore, AuditSigner


async def main():
    store = AuditIntegrityStore(signer=AuditSigner())
    summary = await store.backfill_missing_integrity_records()
    print(
        "audit_logs={audit_logs} "
        "integrity_records_before={integrity_records_before} "
        "created={created} "
        "integrity_records_after={integrity_records_after} "
        "signed={signed} unsigned={unsigned} not_configured={not_configured}".format(**summary)
    )
    if summary["audit_logs"] != summary["integrity_records_after"]:
        print(
            "AUDIT_INTEGRITY_BACKFILL: FAIL "
            f"(mismatch audit_logs={summary['audit_logs']} "
            f"integrity_records_after={summary['integrity_records_after']})"
        )
        sys.exit(1)
    print("AUDIT_INTEGRITY_BACKFILL: PASS")


asyncio.run(main())
PY
