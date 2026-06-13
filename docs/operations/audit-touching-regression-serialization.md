# Audit-Touching Regression Serialization (Stage 44)

Serializes every script that reads or mutates the audit chain so two of them
can never race. Also isolates the tamper simulation and adds a residue detector.

## Root cause of the race observed in Step 41

Step 41 ran the approved restore-exception verify **concurrently** with the
full regression. Both invoke `simulate_audit_tamper_detection.sh`, which:

1. picks the **latest** integrity row,
2. appends ` [TAMPER-SIMULATION]` to its `audit_logs.summary`,
3. re-runs the verifier (which must detect the mismatch),
4. restores the original summary in a `finally` block.

With two simulations interleaving, one sim's "latest" row and another's
restore overlapped, leaving a second ` [TAMPER-SIMULATION]` residue at a new
sequence. The residue was a fresh `test_tamper_not_restored` artifact and had
to be cleared with another controlled restore. Conclusion: audit-touching
scripts must be **serialized**.

## Audit verification lock design

`scripts/lib/audit_verification_lock.sh` provides one **exclusive** lock keyed
`aiagents_audit_verification_exclusive_v1`:

* Mechanism: `flock` on `/tmp/<key>.lock` when available (auto-released on
  process death), with an atomic `mkdir` fallback for portability.
* PostgreSQL has no native *shared* advisory lock and verification frequency is
  low, so one exclusive lock is the conservative choice (serialize over speed).
* Timeout: `AUDIT_VERIFICATION_LOCK_TIMEOUT` (default 300s). On timeout the
  helper emits `AUDIT_VERIFICATION_LOCK: TIMEOUT` and the caller must NOT
  proceed.
* Release is guaranteed by an `EXIT` trap.

Functions: `acquire_audit_exclusive_lock`, `acquire_audit_read_lock` (== exclusive),
`release_audit_lock`, `with_audit_exclusive_lock`, `with_audit_read_lock`,
`assert_no_audit_tamper_residue`, `assert_audit_chain_clean_or_known_blocker`,
`record_lock_metadata`, `fail_if_parallel_audit_mutation_detected`.

Markers: `ACQUIRED` / `INHERITED` / `RELEASED` / `TIMEOUT`.

## Runner lock inheritance (Option A)

`run_full_regression.sh --full` acquires the lock **once**, exports
`AUDIT_VERIFICATION_LOCK_HELD_BY_RUNNER=true`, and runs all audit-touching
child scripts. Each child sees the flag, logs `INHERITED`, and does **not**
re-acquire (avoiding self-deadlock). The runner releases on `EXIT`. `--quick`
mode does not run audit-touching scripts and does not take the lock.

The regression report records `audit_lock_used`, `audit_lock_acquired_at`,
`audit_lock_released`, and `audit_touching_scripts_serialized`.

## Tamper simulation isolation

`simulate_audit_tamper_detection.sh` now:

* acquires the exclusive lock (or inherits it) before doing anything
  (`AUDIT_TAMPER_SIMULATION_LOCKED: PASS`),
* refuses to start if a residue already exists,
* restores the row in a `finally` block (unchanged) and re-verifies,
* runs the residue detector afterwards
  (`AUDIT_TAMPER_SIMULATION_NO_RESIDUE: PASS`),
* FAILS and points to the controlled restore exception if residue remains —
  it never auto-repairs.

## Residue detector

`scripts/detect_audit_tamper_residue.sh` (read-only) counts `audit_logs.summary`
rows containing `[TAMPER-SIMULATION]` and emits only safe fields (count,
audit_log_id, decision_type, task_id, created_at). It runs:

* in `check_runtime_state.sh` (smoke),
* before and after a full regression (full mode),
* after the tamper-evident verify and the restore-exception verify.

`AUDIT_TAMPER_RESIDUE_DETECTOR: PASS` (count 0) / `FAIL` (count > 0).

## Serial execution rules

* The restore exception and the full regression each acquire the exclusive lock.
* A standalone audit-touching script blocks (up to the timeout) if another
  holds the lock, then times out rather than racing.
* `verify_audit_log_restore_exception.sh` owns the lock for its whole run; its
  children (restore + downstream verifiers) inherit it.
* `verify_audit_touching_serialization.sh` runs its child checks **sequentially**
  and deliberately does not hold the lock, so the full-regression child can
  acquire it for real.

## What to do if residue is detected

1. Do **not** manually `UPDATE`/`DELETE` the database.
2. Run the controlled restore exception:
   `AUDIT_LOG_RESTORE_APPROVED=true ./scripts/restore_audit_log_test_tamper_residue.sh`
   (see [audit-log-restore-exception-policy.md](audit-log-restore-exception-policy.md)).
3. Re-run the verifier and the full regression.

## What not to do

* Do not run the restore exception, a tamper simulation, and the full
  regression concurrently.
* Do not auto-repair residue from inside a verify/simulation script.
* Do not lower verifier strictness, relax the denylist, or mark a failed record
  as pass to make a run green.

## How to run a full regression safely

```bash
./scripts/run_full_regression.sh --full --json-report   # takes the lock itself
```

Do not start a second audit-touching script while it runs — the lock will make
the second one wait and (after the timeout) report `audit_lock_timeout`.

## New regression failure classes

`audit_serialization_failure`, `audit_tamper_residue_failure`, and
`audit_lock_timeout` are **disallowed** failures (they count toward
`DISALLOWED_FAIL` and are never treated as an allowed gap or a skipped pass).
Only documented backup-readiness gaps remain `pass_with_gaps`.

## Operations / safety

`/operations/safety` carries `audit_touching_regression_serialized`,
`audit_verification_lock_enabled`, `audit_verification_lock_last_status`,
`audit_tamper_simulation_isolated`, `audit_tamper_residue_detected`,
`audit_tamper_residue_count`, `latest_full_regression_audit_lock_used`, and
`latest_full_regression_audit_touching_serialized`. Read-only endpoints:
`GET /operations/audit/tamper-residue` and
`GET /operations/audit/verification-lock/latest`.

## Current limitations

* The lock is host-level (all audit-touching verification runs on 10.0.1.31).
  A multi-host setup would need a shared/advisory-lock mechanism.
* The lock does not stop the running services (audit-worker) from appending new
  audit rows; it only serializes the *verification/restore* scripts. The tamper
  sim restores by `audit_log_id`, so concurrent worker writes are harmless.
