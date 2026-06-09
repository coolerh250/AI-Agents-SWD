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

## Carry-forward limitations (recorded explicitly, Stage 35+ / Stage 36+)

These two items remain open after Stage 34, Stage 35, **and Stage 36**
and **must not be silently dropped** from future work:

1. **HMAC key rotation / key map loader.** The signer reads a single
   `AUDIT_HMAC_KEY` from env at process start. When an operator
   rotates the key, rows signed with the old key cannot be verified
   by the new key. The schema already records `signing_key_id` per
   row so a future iteration can load a key map (e.g. from a Vault
   path or a SecretProvider keyed by `signing_key_id`). Stage 35 did
   NOT implement this; **Stage 36 did NOT implement this either**.
   The operator-facing workaround is to keep running the verifier
   with the OLD key on the OLD chain section and the NEW key on the
   NEW section.
2. **audit-service direct POST `/audit/events` immediate integrity
   gap.** Audit rows that land via the direct POST handler bypass
   the audit-worker and therefore do NOT pick up an integrity
   record at write time. Today the recovery is the backfill script
   (run after the fact). Future remediation options: (a) move the
   audit-service handler to publish onto `stream.audit` instead of
   writing directly; (b) call `AuditIntegrityStore.create_integrity_record_for_audit_log`
   inline from the audit-service handler. Stage 35 did NOT implement
   either; **Stage 36 did NOT implement either**. The runbook
   recommends running the backfill on the cadence at which the
   direct-POST endpoint is exercised, and the Stage 36 restore drill
   re-walks the chain in the restored DB so an operator can confirm
   the backfill has caught up.

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
