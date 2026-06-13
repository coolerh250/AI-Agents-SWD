# Audit Log Restore Exception Policy (Stage 43)

A narrowly-scoped, operator-approved exception for restoring a single
**test-tampered** ``audit_logs.summary`` so the row re-matches its
already-correct integrity record.

This is the forensically-cleaner alternative to the Stage 42 integrity-record
repair. Stage 42's repair re-binds the integrity chain to the *contaminated*
payload and cascades ``prev_hash`` across the tail. This exception instead
removes the proven tamper residue from the one audit_logs row so the existing,
correct integrity record verifies again — **no integrity-record change, no
cascade**.

> **Hard rule:** this exception modifies ``audit_logs.summary`` for exactly one
> record. It modifies **zero** ``audit_integrity_records`` and never deletes any
> row.

## Allowed restore case

All of the following must hold (validated by the precheck, not assumed):

* forensic ``root_cause_classification == test_tamper_not_restored``.
* ``affected_audit_log_id`` matches the forensic report.
* ``affected_sequence_number`` matches the forensic report.
* the affected row is synthetic / test data.
* ``production_executed == false``.
* the integrity record for the row is proven correct (its stored canonical
  hash equals the hash of the row with the tamper residue removed).
* the restore removes **only** the forensically-proven tamper marker.
* the restore does **not** modify ``audit_integrity_records``.
* the restore does **not** cascade the chain.
* the restore does **not** change canonicalization semantics.

## Disallowed restore case

* ``root_cause == unknown``.
* ``production_executed == true``.
* non-synthetic / production data.
* a security-relevant production audit row.
* any row touching a real secret or real production action.
* the integrity record itself is wrong (that is a Stage 42 repair case, not a
  restore case).
* HMAC key-missing-only failures.
* anything requiring a row deletion to pass.
* anything requiring a broad multi-row ``audit_logs`` change.
* no operator approval flag.

If any precondition fails the procedure stops with
``AUDIT_LOG_RESTORE: REJECTED_UNSAFE`` and makes no DB change.

## Approval

Dry-run by default. A DB change requires the explicit operator flag:

```bash
AUDIT_LOG_RESTORE_APPROVED=true ./scripts/restore_audit_log_test_tamper_residue.sh
```

Without it the tool reports ``AUDIT_LOG_RESTORE: APPROVAL_REQUIRED`` and changes
nothing. The restore must run via the controlled script — never a manual
``psql UPDATE``.

## Evidence

* A redacted snapshot is taken before an approved apply
  (``source/audit-forensics/snapshots/``, gitignored).
* A restore report is written
  (``source/audit-forensics/audit_log_restore_{timestamp}.json`` +
  ``audit_log_restore_latest.json``, gitignored).
* The verifier runs after the restore.
* Full regression runs after the restore.
* The restore action is recorded as a new audit row whose integrity record is
  appended to the chain tail (the latest sequence advances — this is expected
  and does not re-contaminate the chain).
* The report records before/after summary **hashes**, never the raw summary or
  any secret.

## Transaction + rollback

The apply runs in one transaction holding the chain advisory lock:

1. ``UPDATE audit_logs SET summary = <restored> WHERE id = <affected> AND
   summary = <current>`` — must affect exactly one row.
2. recompute the row's canonical hash and assert it now equals the stored
   integrity hash; mismatch raises → ROLLBACK.
3. append the restore audit event + its integrity record.
4. COMMIT.

After commit the full verifier runs (separate connection). Because the
pre-commit hash check already guaranteed correctness, the verifier passes; if
it did not, a manual rollback procedure would be required (the snapshot enables
it).

## Audit / notification handling

* Decision types: ``audit_log_restore_precheck_started|passed|failed``,
  ``audit_log_restore_dry_run``, ``audit_log_restore_approval_required``,
  ``audit_log_restore_started|completed|failed|verified``.
* Notification events (``audit.*`` namespace, denylisted — never real-delivered):
  ``audit.log_restore_approval_required|completed|failed|verified``.
* The restore event passes through the Stage 39 direct-POST integrity closure
  and must not trigger a recursive restore loop.

## Production constraints

* ``production_executed=true`` count must remain ``0``.
* No real LLM / GitHub production / Discord / pager / escalation.
* ``HARD_SAFETY_ACTIONS`` and the delivery denylist are unchanged.
* Claude Code reports observations only and never runs an approved restore on
  the real database without the explicit operator flag.

## Report format

```
restore_id, created_at, dry_run, approved, affected_audit_log_id,
affected_sequence_number, root_cause, restore_type=test_tamper_residue,
before_summary_hash, after_summary_hash, before_contains_tamper_marker,
after_contains_tamper_marker, stored_canonical_payload_hash,
recomputed_after_canonical_payload_hash, hash_match_after,
audit_logs_modified_count, audit_integrity_records_modified_count,
verifier_after_restore, full_regression_after_restore, restore_audit_event_id,
production_executed (false), status, warnings[]
```

``status`` ∈ ``dry_run | approval_required | rejected_unsafe | completed | failed``.
