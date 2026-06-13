# Audit Chain Forensics (Stage 42)

Read-only forensic analysis of the tamper-evident audit integrity chain. The
forensic analyzer locates failing records, recomputes their hashes, classifies
a root cause, and writes a redacted report. **It never mutates the database.**

## How a mismatch is detected

The verifier (`AuditChainVerifier`) walks `audit_integrity_records` joined to
`audit_logs` by `sequence_number` and recomputes, per row:

* `canonical_payload_hash = SHA-256(canonical_json(payload))`
* `row_hash = SHA-256(envelope(chain_version, sequence, audit_log_id, prev_hash, canonical_payload_hash))`

The verifier **stops at the first mismatch** and records
`first_failure_sequence`. The integrity endpoint's `failed_verifications_count`
counts failed verification *runs*, not failed records — a single bad record can
produce many failed runs.

The forensic analyzer (`shared/sdk/audit_integrity/forensics.py`) instead walks
the **whole** chain and collects **every** failing record.

## Failure types

| failure type | meaning |
|---|---|
| `canonical_payload_hash_mismatch` | the current `audit_logs` payload no longer hashes to the stored canonical hash |
| `row_hash_mismatch` | the stored row hash does not match the recomputed envelope |
| `prev_hash_mismatch` | the stored `prev_hash` ≠ the previous record's stored `row_hash` |
| `sequence_gap` | a sequence number is missing |
| `hmac_signature_invalid` | a signed row's HMAC does not verify |
| `hmac_signing_key_missing` | a signed row's `signing_key_id` is absent from the keyring |

## Root cause classification

`classify_chain_root_cause()` aggregates per-record findings into one of:

* `test_tamper_not_restored` — a synthetic test row (e.g. carrying a
  `[TAMPER-SIMULATION]` marker) whose tamper-simulation restore step did not
  complete. **Provable**: stripping the known marker reproduces the stored
  canonical hash, the row is `production_executed=false`.
* `canonicalization_version_drift` — many rows of one `decision_type` all
  mismatch with no tamper marker (canonicalization logic changed).
* `direct_post_legacy_gap` — missing integrity records only (backfill closes it).
* `audit_log_mutated_after_integrity` — canonical mismatch with no proof of
  synthetic origin. **Not repairable** without operator proof.
* `manual_database_change` — `prev_hash` diverges, payload intact.
* `hmac_key_missing_only` — only the signature fails; payload + chain intact.
  **Never repair the payload hash for a key issue.**
* `unknown` — mixed or ambiguous; **repair is blocked.**

Confidence is `high` for a single clean cause, `medium` for a drift cluster,
`low`/`n/a` otherwise.

## Forensic report format

Written to `source/audit-forensics/audit_forensic_{timestamp}.json` and
`audit_forensic_latest.json`. Key fields:

```
report_id, created_at, git_commit, database, verifier_mode,
first_failed_sequence, failed_sequences, failed_records_count,
failed_records[] {                       # one per failing record
  sequence_number, audit_log_id, decision_type, task_id, created_at,
  stored_canonical_payload_hash, recomputed_canonical_payload_hash,
  stored_row_hash, recomputed_row_hash,
  stored_prev_record_hash, expected_prev_record_hash,
  signature_status, signature_verification_status,
  failure_types[], summary_redacted, tamper_marker_detected,
  recovered_original_matches, production_executed,
  suspected_root_cause, repairable, repair_risk
},
failure_cluster_summary, root_cause_classification, confidence,
affected_sequence_range, affected_decision_types,
recommended_action, repair_allowed, repair_risk, repair_policy_reason,
production_executed
```

The report **never** contains an HMAC key, token, or full unredacted payload —
`summary` is truncated and token-scrubbed; the `hmac_signature` column is never
read by the analyzer.

## Safety constraints

* The analyzer is **read-only**. It never writes `audit_logs` or
  `audit_integrity_records`.
* Free text is redacted (`redact_summary`) before it enters a report.
* `repair_allowed` is always set explicitly to `true` or `false`. An `unknown`
  classification forces `repair_allowed=false`.

## How to export a snapshot

```bash
./scripts/export_audit_forensic_snapshot.sh        # reads audit_forensic_latest.json
SNAPSHOT_NEIGHBORS=5 ./scripts/export_audit_forensic_snapshot.sh
```

Snapshots are written to `source/audit-forensics/snapshots/` and are
**gitignored** — they may contain (redacted) full payload rows. The forensic
*report* is redacted and may be referenced; the *snapshot* must not be committed.

## Interpreting `repair_allowed`

`repair_allowed=true` means the forensic verdict matches an allowed repair case
(see [audit-chain-repair-policy.md](audit-chain-repair-policy.md)). It does **not**
mean a repair has run — repair is separately gated behind an explicit operator
approval flag and defaults to dry-run.

## What NOT to repair

* `unknown` root cause.
* `audit_log_mutated_after_integrity` that is not provably synthetic.
* `manual_database_change`.
* Any record with `production_executed=true`.
* Signature-only failures (`hmac_key_missing_only`) — fix the key, not the hash.

## Operations API

* `GET /operations/audit/forensics/latest` — latest forensic report (read-only).
* `GET /operations/audit/forensics/reports` — recent forensic reports.
* `GET /operations/audit/integrity` — now carries `first_failed_sequence`,
  `latest_forensic_report_id`, `latest_forensic_root_cause`, `repair_required`,
  `repair_allowed`, `repair_risk`, `latest_repair_status`.

These endpoints never run a scan or a repair; they read the latest report files.
