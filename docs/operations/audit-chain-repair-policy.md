# Audit Chain Repair Policy (Stage 42)

Controlled repair of the tamper-evident audit integrity chain. A repair
recomputes `audit_integrity_records` so the chain re-binds to the current
(authoritative) `audit_logs` content and cascades `prev_hash` from the first
failed sequence to the chain tail.

> **Hard rule:** a repair modifies `audit_integrity_records` ONLY. It never
> modifies, deletes, or reorders `audit_logs`.

## Allowed repair cases

1. **`test_tamper_not_restored`** — provably synthetic test row (e.g. a
   `[TAMPER-SIMULATION]` marker whose restore did not complete), with
   `production_executed=false`, where stripping the marker reproduces the
   stored canonical hash.
2. **`canonicalization_version_drift`** — a uniform, deterministic drift across
   one `decision_type` that can be re-derived for all affected rows, with
   `production_executed=false`.
3. **`direct_post_legacy_gap`** — *missing* integrity records only; closed by
   `backfill_audit_integrity.sh` (not by this repair tool).
4. A known non-production validation artifact with `production_executed=false`.

## Disallowed repair cases

1. `unknown` root cause.
2. `audit_log_mutated_after_integrity` that is not provably synthetic.
3. `manual_database_change`.
4. A security-relevant audit record that was modified.
5. Any record with `production_executed=true`.
6. Anything involving a real secret or real production action.
7. `hmac_key_missing_only` — never rewrite a payload hash for a key issue.
8. Any case that would require deleting `audit_logs` rows.

If the root cause is `unknown` or the repair risk is `high`, **stop at the
forensic report** — do not modify data.

## Approval flag

Repair is **dry-run by default**. To apply, the operator must set an explicit
flag in the test environment:

```bash
AUDIT_CHAIN_REPAIR_APPROVED=true ./scripts/repair_audit_chain_integrity.sh
```

Without `AUDIT_CHAIN_REPAIR_APPROVED=true`, the tool reports
`approval_required` and makes **no** database change. On the real 10.0.1.31
database an approved repair is **never** run by default.

## Dry-run default

`./scripts/repair_audit_chain_integrity.sh` (no flag) →
`AUDIT_CHAIN_REPAIR: APPROVAL_REQUIRED` or `DRY_RUN`, no DB change. A dry-run
computes the would-be before/after hashes for inspection without writing.

## Snapshot requirement

Before an approved apply the tool writes a redacted snapshot
(`scripts/export_audit_forensic_snapshot.sh` →
`source/audit-forensics/snapshots/`, gitignored) so the pre-repair state is
captured.

## Rollback requirement

The apply runs inside a single transaction holding the chain advisory lock
(`pg_advisory_xact_lock`). After updating the affected records it **re-verifies
the chain on the same connection**; any remaining mismatch raises and the whole
transaction is **rolled back** — no partial repair is ever persisted.

## Post-repair verification

A completed repair must leave the chain verifying cleanly. The repair report
records `verification_after_repair = { passed, first_failure_sequence,
failure_reason }`. `verify_audit_chain_repair_procedure.sh` asserts this when an
approved repair runs.

## Audit / notification handling

* A completed repair emits an `audit_chain_repair_completed` audit row whose own
  integrity record is appended to the chain (the repair action is itself
  tamper-evident). It carries `production_executed=false` and no key value.
* Notification events live in the `audit.*` namespace, which is in
  `DEFAULT_REAL_DELIVERY_DENYLIST` — they are **never** delivered to a real
  Discord channel.
* The repair event must not trigger a recursive repair loop.

## Production constraints

* `production_executed=true` count must remain `0`; a repair never sets it.
* No real LLM / GitHub production / Discord / pager / escalation is involved.
* `HARD_SAFETY_ACTIONS` and the delivery denylist are unchanged.
* Claude Code reports observations only; it does not declare production
  readiness, and it does not run an approved repair on the real database without
  the explicit operator flag.

## Repair report format

`source/audit-forensics/audit_repair_{timestamp}.json` (+ `audit_repair_latest.json`):

```
repair_id, started_at, completed_at, dry_run, approved, forensic_report_id,
root_cause, repair_allowed, repair_risk, first_failed_sequence,
affected_sequences, changed_records_count,
audit_logs_modified (always false), audit_integrity_records_modified,
before_hash_summary[], after_hash_summary[],
verification_after_repair, production_executed (false),
audit_repair_event_id, status, warnings[]
```

`status` ∈ `dry_run | skipped_unsafe | approval_required | completed | failed`.
