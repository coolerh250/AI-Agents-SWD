# Tamper-Evident Audit Chain (Stage 34)

Stage 34 takes the existing `audit_logs` table from "queryable history"
to "queryable + tamper-evident history". The existing table is **not**
modified -- a sibling `audit_integrity_records` table records a
hash chain that an operator can re-verify at any time.

## Threat model

* **In scope.** A DB-side actor (operator, leaked credential, malicious
  contributor) silently mutates one or more rows of `audit_logs`,
  including dropping a row or inserting a forged one. The verifier
  detects this and points at the first divergent sequence number.
* **Out of scope (acknowledged limitations).**
  * A DB-side actor with privileges to update BOTH `audit_logs` AND
    `audit_integrity_records` consistently. The chain alone cannot
    prevent this; what the chain DOES prevent is the silent path --
    every consistent tamper requires touching both tables in lockstep.
  * Replacing the HMAC key without rotating the chain. Future work:
    multi-key rotation + per-row `signing_key_id`-driven verify.
  * Transport-layer attacks on the audit-worker -- those are mitigated
    by the existing Stage 22 dead-letter + retry semantics.

## Architecture

```
audit-worker handle()
  -> AuditStore.write_audit_log(audit_logs)               [Stage 19]
  -> AuditIntegrityStore.create_integrity_record_for_audit_log
        canonical_payload  = build_canonical_payload(audit_row)
        canonical_hash     = SHA-256(canonical_json(canonical_payload))
        prev               = latest integrity record (row_hash)
        sequence_number    = prev.sequence_number + 1  (or 1 for genesis)
        row_hash           = SHA-256(envelope(
                                chain_version, sequence_number,
                                audit_log_id, prev_hash, canonical_hash))
        hmac_signature     = HMAC-SHA256(AUDIT_HMAC_KEY, row_hash)
                             (or NULL when key unset)
  -> audit_integrity_records INSERT
```

## Canonical payload

A canonical payload is the projection of the `audit_logs` row that we
hash. Only the **business-meaning** columns are included:

| column          | source            | notes                                                    |
|-----------------|-------------------|----------------------------------------------------------|
| `audit_log_id`  | `audit_logs.id`   | pins the canonical payload to a specific row             |
| `task_id`       | `audit_logs.task_id` |                                                       |
| `agent`         | `audit_logs.agent`  |                                                        |
| `decision_type` | `audit_logs.decision_type` |                                                  |
| `summary`       | `audit_logs.summary` |                                                       |
| `result`        | `audit_logs.result`  |                                                       |
| `artifact_refs` | `audit_logs.artifact_refs` | dict keys sorted recursively (see canonical.py) |
| `created_at`    | `audit_logs.created_at` | ISO-8601 UTC with offset                          |

The canonical payload is JSON-serialised with `sort_keys=True`,
`ensure_ascii=False`, and `separators=(",", ":")` -- producing
deterministic bytes regardless of dict insertion order. Everything in
the canonical payload is non-secret operational metadata; the canonical
payload is intended to be operator-inspectable.

## Hash chain

* `chain_version` = 1 today. Future rotations bump this and start a
  new chain with `prev_hash = GENESIS`.
* `row_hash` = `SHA-256(envelope)` where envelope is:

  ```
  chain_version=<int>
  sequence_number=<int>
  audit_log_id=<uuid>
  prev_hash=<row_hash of previous row | GENESIS>
  canonical_payload_hash=<sha256 of canonical JSON>
  ```

* The first row uses `prev_hash = NULL` in the database but the
  envelope substitutes `GENESIS` so the hash is fully determined.

Implementation: `shared/sdk/audit_integrity/hasher.py`.

## Signed receipt / HMAC behavior

The signer reads `AUDIT_HMAC_KEY` from env (or a future SecretProvider).
Behavior:

| key present | `signature_status`            | `hmac_signature` | `signing_key_id`        |
|-------------|-------------------------------|------------------|-------------------------|
| no          | `signing_key_not_configured`  | `NULL`           | `unsigned`              |
| yes         | `signed`                      | hex SHA-256 HMAC | `AUDIT_HMAC_KEY_ID` or `default-test-key-id` |

The key value is **never** returned, logged, echoed in audit, exposed
via any operations endpoint, or written to any artifact. The
`signing_key_id` is opaque metadata and is safe to surface.

When the key is absent the hash chain still provides tamper evidence;
the chain just cannot prove "who signed it." Operators can enable HMAC
later by setting `AUDIT_HMAC_KEY` -- new rows will be signed, and
existing unsigned rows remain valid (no migration required).

## Backfill

For an existing `audit_logs` table without integrity records:

```bash
./scripts/backfill_audit_integrity.sh
```

The script is idempotent. Audit rows already covered by an integrity
record are skipped; the chain extends in `created_at ASC, id ASC` order
so reruns produce identical hashes. The script ends with:

```
audit_logs=... integrity_records_before=... created=...
integrity_records_after=... signed=... unsigned=... not_configured=...
AUDIT_INTEGRITY_BACKFILL: PASS
```

## Verify the chain

```bash
./scripts/verify_audit_integrity.sh
```

Walks both tables joined on `audit_log_id`, ordered by
`sequence_number`. On the first divergence it prints:

```
first_failure_sequence: <int>
first_failure_audit_log_id: <uuid>
failure_reason: canonical_payload_hash_mismatch | row_hash_mismatch |
                 prev_hash_mismatch | hmac_signature_invalid |
                 sequence_gap
expected_hash: <hex>
actual_hash: <hex>
AUDIT_INTEGRITY_VERIFY: FAIL
```

A pass writes one row into `audit_chain_verification_runs` with
`status=passed`. A `partial` status means the chain itself is intact
but some `audit_logs` rows lack an integrity record -- run the
backfill again. The verifier never auto-repairs.

## Tamper detection smoke

```bash
./scripts/simulate_audit_tamper_detection.sh
```

Within a transaction, the script:

1. baseline-verifies the chain,
2. mutates one `audit_logs.summary` row,
3. re-runs the verifier and confirms it reports a mismatch,
4. ROLLBACK so the mutation is discarded,
5. re-verifies to confirm the chain is intact again.

The script ends with `AUDIT_TAMPER_DETECTION_SMOKE: PASS` only when
every phase succeeds, including the post-rollback re-verify.

## Operations endpoints

* `GET /operations/audit/integrity` -- summary block: chain version,
  total audit logs, total integrity records, latest sequence number,
  latest row hash, HMAC enabled, signing key id, latest verification
  status, missing integrity record count, `audit_integrity_degraded`.
  Never includes a key value.
* `POST /operations/audit/verify-chain` -- runs the verifier inline
  and records one `audit_chain_verification_runs` row. Returns the
  full result dict.
* `GET /operations/audit/verify-chain/latest` -- returns the most
  recent `audit_chain_verification_runs` row.
* `GET /operations/audit/receipt/{audit_log_id}` -- per-row receipt:
  sequence number, prev hash, row hash, canonical payload hash,
  `hmac_signature_present` boolean, `hmac_signature_preview` (max 8
  hex characters), `signing_key_id`, created_at,
  `verification_status`. **Never returns the full HMAC signature.**

`GET /operations/safety` additionally surfaces:
`audit_integrity_enabled`, `audit_chain_latest_status`,
`audit_integrity_degraded`, `audit_hmac_enabled`,
`audit_last_verification_at`, `audit_missing_integrity_records`,
`audit_tamper_detected`.

`GET /operations/summary` carries an `audit_integrity_summary` block.

## Metrics

| Prometheus counter                                     | labels                                | meaning                                                                  |
|--------------------------------------------------------|---------------------------------------|--------------------------------------------------------------------------|
| `audit_integrity_records_total`                        | `chain_version`, `status`             | one per integrity-record write                                          |
| `audit_integrity_missing_total`                        | `reason`                              | observed missing integrity records                                       |
| `audit_integrity_verification_runs_total`              | `chain_version`, `status`             | one per verify-chain pass                                                |
| `audit_integrity_verification_failed_total`            | `reason`                              | failed verifications (per `failure_reason`)                              |
| `audit_integrity_degraded_total`                       | `reason`                              | per audit-worker integrity-write failure                                 |
| `audit_tamper_detected_total`                          | `reason`                              | per detected tamper                                                      |

Spans:

* `audit_integrity.canonicalize`
* `audit_integrity.hash`
* `audit_integrity.sign`
* `audit_integrity.persist`
* `audit_integrity.verify_chain`
* `audit_integrity.backfill`
* `audit_integrity.detect_tamper`

Span attributes: `audit_log_id`, `sequence_number`, `chain_version`,
`verification_status`.

## No notification loop

The integrity write path does **not** call `publish_audit_event` or
`publish_notification`. The Stage 32 default-deny stream policy is
unaffected -- even if it ever did, a `discord_real_delivery_blocked`
audit row would not be re-broadcast back onto `stream.notifications`.

Audit decision types reserved for Stage 34:

* `audit_integrity_backfilled`
* `audit_integrity_verified`
* `audit_integrity_failed`
* `audit_integrity_degraded`
* `audit_tamper_detected`

Notification events reserved for Stage 34 (default-blocked by Stage 33
policy):

* `audit.integrity_verified`
* `audit.integrity_failed`
* `audit.tamper_detected`

When invoked, these events log a single summary entry per verify-chain
pass -- never one-per-row.

## Key rotation (future work)

The chain carries `signing_key_id` per row, so an operator who rotates
`AUDIT_HMAC_KEY` can keep old rows verifiable with the previous key
and start a new sub-chain with the new key. The current verifier only
holds one key in process; a future iteration will load the key map
keyed by `signing_key_id` (out of scope for Stage 34).

## Stage 39 -- HMAC keyring rotation + direct POST integrity closure

Stage 39 closes the two carry-forward gaps recorded under Stages 34-36.
The remediation is **additive**: existing `audit_logs`,
`audit_integrity_records`, and `audit_chain_verification_runs` rows
are untouched. Existing chain hashes / signatures keep verifying with
the same logic.

### HMAC keyring (`shared/sdk/audit_integrity/keyring.py`)

The signer is now backed by an in-process keyring. Configuration is
read from env at process start; the **key value is never logged or
surfaced via any API**:

| Env var                    | Effect                                                                 |
|----------------------------|------------------------------------------------------------------------|
| `AUDIT_HMAC_KEYRING_JSON`  | Multi-key JSON document (preferred). See shape below.                  |
| `AUDIT_HMAC_ACTIVE_KEY_ID` | Override the `active_key_id` field of the keyring JSON.                |
| `AUDIT_HMAC_KEY`           | Legacy single-key fallback. ID = `AUDIT_HMAC_KEY_ID` or `legacy-single-key`. |
| (neither set)              | Mode = `none`. Chain stays unsigned; verification still passes.        |

`AUDIT_HMAC_KEYRING_JSON` shape (dummy placeholder values shown — do
not put real keys in source):

```json
{
  "active_key_id": "audit-key-2026-06",
  "keys": {
    "audit-key-2026-05": "<base64-or-plain-secret-placeholder>",
    "audit-key-2026-06": "<base64-or-plain-secret-placeholder>"
  }
}
```

Keyring modes:

| Mode                | When                                                                         |
|---------------------|------------------------------------------------------------------------------|
| `none`              | Neither env var set. Chain is unsigned; chain verify passes.                 |
| `legacy_single_key` | `AUDIT_HMAC_KEY` present, JSON absent.                                       |
| `multi_keyring`     | Valid `AUDIT_HMAC_KEYRING_JSON` loaded.                                      |
| `invalid`           | JSON malformed, `active_key_id` not in `keys`, or values empty. Signing is **refused** so the wrong key never enters the chain. |

Per-row verification looks up the key by the row's recorded
`signing_key_id`, **not** by the currently-active key. A row signed
with `audit-key-2026-05` still verifies after the active key has
rotated to `audit-key-2026-06`, provided the old key remains in the
keyring.

### Key-status metadata table

Migration `015_audit_integrity_key_rotation.sql` adds
`audit_hmac_key_metadata`:

| Column              | Meaning                                                       |
|---------------------|---------------------------------------------------------------|
| `key_id`            | Opaque keyring identifier (never the key value).              |
| `key_status`        | `active` / `inactive` / `retired` / `missing` / `invalid`.    |
| `source`            | `legacy_env` / `keyring_env` / `secret_provider` / `unknown`. |
| `first_seen_at`     | When this process first observed the key_id.                  |
| `last_seen_at`      | Updated on each keyring upsert.                               |
| `active_from` / `active_until` | Lifecycle bookkeeping per key_id.                  |

`GET /operations/audit/keyring` upserts those rows opportunistically
and returns the table verbatim — never the key bytes.

### Verification modes (`AUDIT_VERIFY_SIGNATURE_MODE`)

| Mode          | Behaviour                                                                       |
|---------------|---------------------------------------------------------------------------------|
| `permissive`  | Hash-chain must pass. Signed rows verify when the key is present; missing keys downgrade to `partial` + add a warning. Unsigned rows allowed. Default. |
| `strict`      | Hash-chain must pass. Signed rows must verify and the key must be in the keyring. Unsigned rows fail unless `AUDIT_VERIFY_ALLOW_UNSIGNED_LEGACY=1`. Recommended for production. |
| `chain_only`  | Hash-chain only — HMAC is ignored. Emergency diagnostic.                       |

`POST /operations/audit/verify-chain` accepts an explicit `mode` via
either the JSON body (`{"mode":"strict"}`) or a query parameter
(`?mode=strict`).

### Direct POST integrity closure

`POST /audit/events` on the audit-service now inserts the `audit_logs`
row and the matching `audit_integrity_records` row **inside the same
Postgres transaction**:

1. `async with conn.transaction():`
2. `INSERT INTO audit_logs ... RETURNING ...`
3. `SELECT pg_advisory_xact_lock(hashtext('audit_integrity_chain_v1'))`
   to serialise the sequence assignment.
4. `INSERT INTO audit_integrity_records ...` via
   `create_integrity_record_in_txn`.
5. publish `audit.recorded` on `stream.audit` (best-effort).
6. respond `200` with `audit_integrity_created=true` and the
   `audit_integrity_status` label.

On any failure inside the transaction the whole txn rolls back, the
audit-service responds **`503`**, and `audit_logs` is left untouched —
no orphan row to backfill. The
`audit_direct_post_integrity_failures_total` counter is incremented
with the exception class so an operator can diagnose.

### Concurrency / sequence lock

`create_integrity_record_in_txn` is the single shared writer used by
the audit-worker stream path, the direct POST path, and the backfill
script. Each call acquires
`pg_advisory_xact_lock(hashtext('audit_integrity_chain_v1'))` before
reading the latest `sequence_number`, so two concurrent writers cannot
allocate the same sequence. On a unique-constraint conflict the writer
retries up to 5 times — the retry counter is exposed as
`audit_integrity_concurrency_retries_total`.

### Backfill — recovery only

`backfill_audit_integrity.sh` now reports both `missing_before` and
`missing_after`. With direct POST closure in place, the normal steady
state should be `missing_before=0` and the script becomes a no-op.
Recovery semantics are retained for unusual scenarios (e.g. a restored
backup taken mid-transaction). The backfill never forges signatures
for rows whose original key is unknown — it asks the signer to sign,
and the signer reports `signing_key_not_configured` when the keyring
is empty.

### Operational key rotation procedure

1. Add the new key to `AUDIT_HMAC_KEYRING_JSON.keys` while keeping the
   old key entries in place.
2. Restart the audit-service so the signer rebuilds its keyring.
3. New rows sign with the new active key; historical rows still verify
   because their `signing_key_id` points at the still-present old key.
4. After enough verification runs in `strict` mode have passed on the
   new active key, decommission the old key by dropping it from
   `AUDIT_HMAC_KEYRING_JSON.keys`. The metadata table moves the old
   `key_id` to `inactive` automatically.

### Operations endpoints (Stage 39 additions)

* `GET /operations/audit/integrity` — now includes
  `hmac_keyring_configured`, `hmac_keyring_mode`, `hmac_keyring_valid`,
  `active_signing_key_id`, `known_key_ids`, `signed_records`,
  `unsigned_records`, `key_missing_records`, `signature_failed_records`,
  `latest_verification_mode`, `direct_post_integrity_enabled`,
  `direct_post_missing_integrity_records`,
  `audit_integrity_writer_locking_enabled`.
* `GET /operations/audit/keyring` — read-only keyring view. Returns
  `mode`, `valid`, `active_key_id`, `known_key_ids`, `invalid_reason`,
  the `audit_hmac_key_metadata` rows, and per-key signed-record counts.
  **Never returns key bytes.**
* `GET /operations/audit/receipt/{audit_log_id}` — now carries
  `signing_key_id`, `signature_status`, `signature_verification_status`
  (`ok` / `key_missing` / `signature_failed` / `no_keyring` / `n/a`),
  `key_available`, `keyring_mode`.
* `POST /operations/audit/verify-chain?mode=<mode>` — accept a
  verification mode (JSON body also accepted).
* `GET /operations/safety` — new flags:
  `audit_hmac_keyring_configured`, `audit_hmac_keyring_valid`,
  `audit_hmac_keyring_mode`, `audit_hmac_active_signing_key_id`,
  `audit_hmac_rotation_supported`, `audit_direct_post_integrity_enabled`,
  `audit_direct_post_integrity_gap_closed`,
  `audit_integrity_concurrency_lock_enabled`,
  `audit_integrity_strict_verify_ready`,
  `audit_signature_key_missing_count`.

### Metrics (Stage 39 additions)

* `audit_hmac_keyring_load_total{mode,source}`
* `audit_hmac_keyring_invalid_total{reason}`
* `audit_signature_verified_total{mode,signing_key_id}`
* `audit_signature_failed_total{mode,reason}`
* `audit_signature_key_missing_total{mode}`
* `audit_direct_post_integrity_created_total{status}`
* `audit_direct_post_integrity_failures_total{reason}`
* `audit_integrity_sequence_lock_wait_seconds` (histogram)
* `audit_integrity_concurrency_retries_total{reason}`

### Audit / notification vocabulary

Decision types reserved for Stage 39: `audit_hmac_keyring_loaded`,
`audit_hmac_keyring_invalid`, `audit_hmac_key_rotated`,
`audit_signature_verified`, `audit_signature_key_missing`,
`audit_direct_post_integrity_created`,
`audit_direct_post_integrity_failed`,
`audit_integrity_concurrency_verified`.

Notification events: `audit.keyring_loaded`,
`audit.keyring_invalid`, `audit.direct_post_integrity_created`,
`audit.direct_post_integrity_failed`,
`audit.signature_key_missing`. These stay under the `audit.*`
namespace and remain in the Stage 32 default real-delivery denylist.

### How to verify Stage 39

```bash
./scripts/verify_audit_hmac_key_rotation.sh
./scripts/verify_audit_direct_post_integrity.sh
./scripts/verify_audit_integrity_remediation.sh
./scripts/check_runtime_state.sh | grep -E 'AUDIT_KEYRING|AUDIT_DIRECT_POST|AUDIT_HMAC_ROTATION|AUDIT_SIGNATURE_VERIFY|AUDIT_INTEGRITY_CONCURRENCY'
```

`verify_audit_integrity_remediation.sh` ends with
`AUDIT_INTEGRITY_REMEDIATION_VERIFY: PASS` when every phase succeeded.

## Carry-forward limitations (after Stage 39)

The two original carry-forward items are **closed** by Stage 39:

1. ~~HMAC key rotation / key map loader.~~ **Closed** by the
   `AuditHmacKeyring` loader + per-row `signing_key_id` verification.
2. ~~audit-service direct POST `/audit/events` immediate integrity gap.~~
   **Closed** by the in-transaction integrity writer + `503`/rollback
   on failure.

The following items remain open and **must not be silently dropped**:

* Backup / DR gaps: `encryption_no_key`, `storage_not_off_host`,
  `schedule_dry_run_only`, `migration_down_gaps`.
* Kubernetes / Helm / ArgoCD runtime baseline.
* Incident response runbook / external alert receiver.
* Real production secret store / real off-host backup target. Stage 39
  uses environment variables; a production deployment must source the
  keyring from a real secret store (Vault, KMS, etc.) and never via env
  on the running pods.

## How to verify (end-to-end)

```bash
./scripts/backfill_audit_integrity.sh
./scripts/verify_audit_integrity.sh
./scripts/simulate_audit_tamper_detection.sh
./scripts/verify_tamper_evident_audit.sh
./scripts/check_runtime_state.sh | grep -E 'AUDIT_INTEGRITY|AUDIT_RECEIPT|AUDIT_TAMPER'
```

`verify_tamper_evident_audit.sh` ends with
`TAMPER_EVIDENT_AUDIT_VERIFY: PASS` when every phase succeeded,
including production-safety counters at 0/0 and no secret leak in any
operations response.

## Stage 42 -- forensics + controlled repair

When the verifier reports a persistent mismatch, the Stage 42 forensic
analyzer classifies the root cause and (when provably safe and explicitly
approved) a controlled repair can re-bind `audit_integrity_records` to the
current `audit_logs` content. The repair modifies integrity records only,
never `audit_logs`, defaults to dry-run, and re-verifies inside a transaction
with rollback on failure. See
[audit-chain-forensics.md](audit-chain-forensics.md) and
[audit-chain-repair-policy.md](audit-chain-repair-policy.md).

Note on the tamper-detection smoke: `simulate_audit_tamper_detection.sh`
appends a `[TAMPER-SIMULATION]` marker to the latest row, confirms the
verifier detects it, then restores the row in a `finally`. If that restore
does not complete (process killed), the marker is left in place and surfaces
later as a `test_tamper_not_restored` forensic finding.
