#!/usr/bin/env bash
# Stage 39 -- HMAC key rotation verify.
#
# Drives the in-process keyring loader + signer + verifier through three
# scenarios (no key / legacy single key / multi-key rotation) and asserts:
#
#   * no-key   : signer is unconfigured, sign() returns
#                signing_key_not_configured, chain verification still passes.
#   * legacy   : signer signs new rows with the legacy key id, signatures verify.
#   * rotation : old rows verify with the old key id even after a new active
#                key is loaded; strict mode reports key_missing when the old key
#                is dropped.
#
# Never prints AUDIT_HMAC_KEY / AUDIT_HMAC_KEYRING_JSON content.
# Marker: AUDIT_HMAC_KEY_ROTATION_VERIFY: PASS / FAIL.

set -uo pipefail

cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"

$PY - <<'PY'
import json
import sys

sys.path.insert(0, ".")

from shared.sdk.audit_integrity import (
    AuditHmacKeyring,
    AuditSigner,
    KEYRING_MODE_LEGACY_SINGLE_KEY,
    KEYRING_MODE_MULTI_KEYRING,
    KEYRING_MODE_NONE,
    VERIFY_OUTCOME_KEY_MISSING,
    VERIFY_OUTCOME_OK,
)


def fail(reason: str) -> None:
    print(f"AUDIT_HMAC_KEY_ROTATION_VERIFY: FAIL ({reason})")
    sys.exit(1)


# Scenario A -- no key configured.
none_kr = AuditHmacKeyring(env={})
if none_kr.mode != KEYRING_MODE_NONE:
    fail("no_key_mode_not_none")
signer = AuditSigner(keyring=none_kr)
sig, status, key_id = signer.sign("row-hash-a")
if sig is not None or status != "signing_key_not_configured" or key_id != "unsigned":
    fail("no_key_unexpected_sign_result")
print("A: AUDIT_HMAC_NO_KEY: PASS (mode=none, status=signing_key_not_configured)")

# Scenario B -- legacy single key.
legacy_kr = AuditHmacKeyring(
    env={"AUDIT_HMAC_KEY": "test-only-secret-do-not-deploy-ABCDEF", "AUDIT_HMAC_KEY_ID": "kid-legacy"}
)
if legacy_kr.mode != KEYRING_MODE_LEGACY_SINGLE_KEY:
    fail("legacy_mode_not_set")
if legacy_kr.active_key_id != "kid-legacy":
    fail("legacy_active_key_id_mismatch")
signer_b = AuditSigner(keyring=legacy_kr)
sig_b, status_b, kid_b = signer_b.sign("row-hash-b")
if status_b != "signed" or kid_b != "kid-legacy" or not sig_b:
    fail("legacy_signing_unexpected")
ok_b, outcome_b = signer_b.verify_with(
    row_hash="row-hash-b", signature=sig_b, signing_key_id=kid_b
)
if not ok_b or outcome_b != VERIFY_OUTCOME_OK:
    fail("legacy_verify_unexpected")
print("B: AUDIT_HMAC_LEGACY_SINGLE_KEY: PASS (status=signed, signing_key_id=kid-legacy)")

# Scenario C -- multi-keyring rotation.
payload_v1 = {"active_key_id": "kid-v1", "keys": {"kid-v1": "secret-v1-do-not-deploy"}}
kr_v1 = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": json.dumps(payload_v1)})
if kr_v1.mode != KEYRING_MODE_MULTI_KEYRING or kr_v1.active_key_id != "kid-v1":
    fail("rotation_v1_mode_or_active_mismatch")

signer_v1 = AuditSigner(keyring=kr_v1)
sig_v1, status_v1, kid_v1 = signer_v1.sign("row-v1")
if status_v1 != "signed" or kid_v1 != "kid-v1":
    fail("rotation_v1_sign_unexpected")

# Rotate: keep kid-v1, add kid-v2, switch active to kid-v2.
payload_v2 = {
    "active_key_id": "kid-v2",
    "keys": {
        "kid-v1": "secret-v1-do-not-deploy",
        "kid-v2": "secret-v2-do-not-deploy",
    },
}
kr_v2 = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": json.dumps(payload_v2)})
if kr_v2.active_key_id != "kid-v2":
    fail("rotation_v2_active_not_v2")
signer_v2 = AuditSigner(keyring=kr_v2)
sig_v2, status_v2, kid_v2 = signer_v2.sign("row-v2")
if kid_v2 != "kid-v2":
    fail("rotation_v2_sign_key_mismatch")

# OLD row still verifies (we look up by signing_key_id).
ok_old, outcome_old = signer_v2.verify_with(
    row_hash="row-v1", signature=sig_v1, signing_key_id=kid_v1
)
if not ok_old or outcome_old != VERIFY_OUTCOME_OK:
    fail("rotation_old_row_unverifiable_after_rotation")

# Drop the old key. Verifying an old row should now report key_missing.
payload_v3 = {
    "active_key_id": "kid-v2",
    "keys": {"kid-v2": "secret-v2-do-not-deploy"},
}
kr_v3 = AuditHmacKeyring(env={"AUDIT_HMAC_KEYRING_JSON": json.dumps(payload_v3)})
signer_v3 = AuditSigner(keyring=kr_v3)
ok_dropped, outcome_dropped = signer_v3.verify_with(
    row_hash="row-v1", signature=sig_v1, signing_key_id=kid_v1
)
if ok_dropped or outcome_dropped != VERIFY_OUTCOME_KEY_MISSING:
    fail("rotation_dropped_key_not_detected")

# Defensive belt: rendering any keyring snapshot must never expose key bytes.
for kr in (legacy_kr, kr_v1, kr_v2, kr_v3):
    flat = json.dumps(kr.snapshot().to_safe_dict())
    for value in (
        "test-only-secret-do-not-deploy-ABCDEF",
        "secret-v1-do-not-deploy",
        "secret-v2-do-not-deploy",
    ):
        if value in flat:
            fail("key_value_leaked_in_snapshot")

print("C: AUDIT_HMAC_MULTI_KEY_ROTATION: PASS (old row verified by old kid, missing key detected)")
print("AUDIT_HMAC_KEY_ROTATION_VERIFY: PASS")
PY
