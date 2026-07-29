# Step 66C.4-BE3-RA-1R — Independent Migration / Rollback / Locking Review

> **Independent review artifact. Written by a reviewer who did NOT implement RA-1A. Every
> conclusion is re-derived from the committed migration SQL, `migration_runner.py`, and direct
> experiments against an isolated ephemeral PostgreSQL 16 — not from RA-1A's own self-verifier or
> records. This review authorizes NO shared migration, NO deployment, NO feature-gate change, NO
> activation. It does not modify `migration_runner.py`, any `migrations/*.sql`, or the RA-1A test
> suite. It does not merge any branch or PR #21.**

## Markers (never conflated)

```text
Process marker (artifacts/process complete): STEP66C4_BE3_RA1_INDEPENDENT_REVIEW_VERIFY: PASS
Technical verdict (independent judgment):     RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

The isolated rehearsal that RA-1A actually executed is correct and its claims re-derive
independently. The `REMEDIATION_REQUIRED` verdict is scoped to the **future shared-apply readiness
foundation** — specifically the new `migration_runner.py`. Migrations 031-035 themselves have no
blocking defect, existing data is fully preserved, and the pre-activation-down boundary is correct
and correctly documented. Nothing was activated; the safety boundary held.

## Scope reviewed

```text
Reviewed baseline (main):  18f11fe
Reviewed feature head:     27184b5   (PR #21, Draft/OPEN/unmerged — confirmed before and after)
Review diff:               18f11fe..27184b5 (migration_runner.py +102 lines; docs/tests/scripts;
                           NO migrations/*.sql changed — 029-035 pre-existed on baseline)
```

All PostgreSQL work ran on an isolated ephemeral PostgreSQL 16.14 container on an internal test
runtime (distinct container name and port from the implementation session's), created for this
review and destroyed afterward. The shared stack was never touched.

## Verdict summary

| Objective | Judgment |
|---|---|
| 1. Migrations 031-035 safe to apply in sequence | PASS — additive, idempotent, correct FK chain, no rewrite/backfill |
| 2. Runner serializes concurrent apply + cleans up in every path | PARTIAL — serialization correct; **cleanup unsafe on the failure path** (H-1) |
| 3. Transaction state recoverable after failure | Data-wise yes; **runner issues no ROLLBACK; connection left aborted** (H-1) |
| 4. Pre-activation down valid only with no runtime data, correctly documented | PASS — not overclaimed anywhere |
| 5. Post-write operational rollback preserves data | PASS — non-destructive, data survives |
| 6. Old-version compatibility substantiated (not one SELECT) | PASS — exercised via `SELECT *`, explicit column list, and read+write |
| 7. Fingerprint deterministic + detects real drift | PARTIAL — deterministic; 5/6 mutation types detected; **FK-action + CHECK-expr blind spots** (M-1) |

## Findings

### H-1 (High, blocks shared-apply) — `apply_chain_locked` does not roll back or release its lock on the failure path; it masks the real error

`apply_chain_locked` (migration_runner.py:36-52) acquires a session-level advisory lock, applies
each file, and in a `finally` block calls `pg_advisory_unlock`. There is **no `ROLLBACK` on any
path**. Each migration file is its own `BEGIN; … COMMIT;`. When a statement inside a file fails,
PostgreSQL aborts that file's transaction and leaves the session in `idle in transaction (aborted)`
state. The `finally` block then runs `SELECT pg_advisory_unlock(…)` **on that aborted connection**,
which itself raises `InFailedSQLTransactionError` (`25P02`).

Empirically confirmed (my `test_rev_apply_chain_locked_failure_path_characterization`, and probe):

```text
apply_chain_locked on a failing chain raises:  InFailedSQLTransactionError
  -> the real migration error (e.g. the actual failing DDL) is MASKED / never surfaced
lock still held while the connection stays open:  TRUE  (finally-unlock never succeeded)
connection reusable without an external ROLLBACK:  FALSE (left aborted)
partial (half-built) table survived:             FALSE (the file's own txn rolled back — good)
lock released after the connection is closed:     TRUE  (only via session teardown, not the runner)
```

Why it matters for shared-apply:
- The module docstring claims "The lock is released even if a migration fails partway through the
  chain." That claim is **not honored by the code** — the release mechanism it relies on
  (`pg_advisory_unlock` in `finally`) provably fails on the exact path it exists for. The lock is
  released only incidentally, when the connection is torn down (or an asyncpg pool's `reset()` runs
  `ROLLBACK` + `pg_advisory_unlock_all()`).
- **Operator diagnostics are actively degraded**: the operator sees "current transaction is aborted"
  instead of the real cause of the migration failure.
- With a **pooled** connection that is returned without a reset, the connection would be poisoned
  (aborted) and the lock leaked — a future shared-apply hazard (§6.7 of the review spec).
- Per the review spec §6/§20, "a failed transaction is explicitly rolled back and the connection is
  safely reusable after" is a required property; the runner does not provide it.

Notably, RA-1A's own evidence record (lines 55-64) **documents this exact operational requirement**
("a runner must issue `ROLLBACK` (or reconnect) after a failed apply before reusing the same
connection") — but the requirement was not applied to the runner it shipped. RA-1A's own suite never
exercises `apply_chain_locked` to failure (its failure tests call `conn.execute(broken)` directly and
bypass the runner), so this gap was never surfaced by its own tests.

Suggested remediation (for the PO/implementation session, NOT performed here): wrap the loop body so
that on any `BaseException` the runner issues an explicit `ROLLBACK` (tolerating its own failure)
**before** attempting `pg_advisory_unlock`, and re-raise the original exception (not the unlock's).
Guarantee unlock runs on a clean session.

### M-1 (Medium, blocks shared-apply) — `schema_fingerprint` blind spots: FK referential actions, CHECK expressions, deferrability

`schema_fingerprint` (migration_runner.py:83-102) captures, per table: columns
(`column_name, data_type, is_nullable, column_default`), constraints (`constraint_name,
constraint_type` only), and indexes (`indexname, indexdef` full text). Mutation testing
(my `test_rev_fingerprint_mutation_detection`) confirms:

```text
DETECTED (fingerprint differs):   drop index; change partial-index predicate; change nullability;
                                  add CHECK (new name); change column DEFAULT
NOT DETECTED (fingerprint equal): change a FK's ON DELETE action (same constraint name);
                                  change a CHECK constraint's expression body (same name)
```

Because only `(constraint_name, constraint_type)` is captured, any change to a constraint's
**semantics** that keeps its name — FK `ON DELETE`/`ON UPDATE` referential action, CHECK expression,
or constraint **deferrability** — is invisible to the fingerprint. This is a real drift-detection
gap for future shared-apply (an operator comparing two fingerprints would see "identical" for a
schema that differs in referential behavior). The review spec §10 mandates recording this as at
least Medium. Coverage of columns/types/nullability/defaults and full index definitions (including
partial predicates and index expressions, via `indexdef` text) is adequate.

### M-2 (Medium, blocks shared-apply) — no migration ledger / no version provenance

There is no `schema_migrations` / `migration_history` / ledger table anywhere in the repository or
in `shared/sdk/backup_dr/`. "Applied" is determined entirely by schema introspection
(`to_regclass(...) IS NOT NULL`). Consequences, evaluated independently:

```text
drift detection:        existence-only checks cannot see a manually-altered column at all; a full
                        golden-fingerprint comparison catches most drift, but (a) no golden
                        fingerprint is stored anywhere, and (b) the M-1 blind spots would still pass.
partial-object:         a half-finished object IS caught in practice, because a later statement /
                        dependent migration fails loudly (confirmed: a foreign wrong-shaped
                        `resume_replay_authorizations (id int)` makes real 032's index creation fail
                        with UndefinedColumnError — not silently accepted). But a *table that exists*
                        is treated as "done" with no check that its shape matches the file on disk.
version provenance:     NONE. If a table exists, nothing records which migration file/version created
                        it or whether it matches the current file on disk. There is no way to tell
                        "was this created by 032 as it exists today, or an older 032?".
operator diagnostics:   an ambiguous state (table exists but shape unknown) yields no diagnostic
                        beyond "exists"; the operator has no provenance to reason from.
```

This is acceptable for the *isolated rehearsal* (each run drops and rebuilds from a known baseline),
but it is a genuine gap for any future shared-apply and must be closed (a ledger, or a stored
golden fingerprint per migration, plus a shape-match check) before a shared apply is authorized.

### M-3 (Medium, blocks shared-apply) — no bounded lock-wait / statement timeout / operational model

`apply_chain_locked` uses blocking `pg_advisory_lock`. A **crashed** holder releases the lock (session
end — verified), but a **hung** holder (long DDL, stuck transaction) with no `lock_timeout` or
`statement_timeout` blocks every waiter **forever**. The runner sets no `lock_timeout`,
`statement_timeout`, or `idle_in_transaction_session_timeout`, and offers no dry-run, plan output,
current/target schema reporting, expected-fingerprint comparison, or structured audit record. A
non-zero failure signal does exist (the call raises), so a CLI wrapper could exit non-zero — but the
raised exception is the masked one from H-1, so the signal's diagnostic content is wrong. Per review
spec §14, bounded lock-wait and bounded statement timeout are FUTURE shared-apply blockers.

### L-1 (Low) — down-script CASCADE asymmetry

`031_..._down.sql` drops its table **without** `CASCADE` (so it fails closed if run out of reverse
order while `replay_requests` (034) still references the outbox — good). `032`–`035` down scripts use
`DROP TABLE … CASCADE`, which — only if run out of the intended reverse order — would silently drop
dependent FK constraints on still-present tables. In the intended reverse order (035→031) the down
chain is coherent and safe; this is a latent foot-gun for a mis-ordered manual down, not a defect in
the rehearsed path.

### L-2 (Low / clarification) — "no partial schema" means no half-built object, not chain atomicity

Because every migration file self-`COMMIT`s, a chain that fails at file N leaves files 1..N-1
committed. This is not corruption (each object is complete) and recovery is an idempotent reapply,
but operators must understand the chain is **not** all-or-nothing across files. RA-1A's records are
accurate on this; stated here for completeness.

## What re-derived cleanly (no defect)

```text
- 031-035 dependency chain (read from the actual CREATE/REFERENCES statements, not prose):
    031 ALTERs operator_clarification_requests (030) + outbox FKs -> 029 & 030
    032 has NO foreign key at all (resource_id deliberately unbound)
    033 -> resume_replay_authorizations (032), operator_clarification_requests (030), operator_tasks (029)
    034 -> resume_replay_authorizations (032) AND clarification_lifecycle_outbox (031)
    035 -> optional/nullable FK to resume_replay_authorizations (032)
  Numeric filename order and FK dependency never contradict.
- Out-of-order apply fails closed (033 before 032 -> UndefinedTableError; no partial resume_requests).
- Duplicate invocation is genuinely idempotent (full chain reapplied -> identical fingerprint), via
  real CREATE ... IF NOT EXISTS / guarded ADD CONSTRAINT — not an error swallowed anywhere.
- Ambiguous-commit recovery: applying the same real file twice yields an identical fingerprint, so a
  blind reapply after an unknown-outcome COMMIT resolves safely (idempotent DDL). A live "commit
  succeeded on server, client never saw the ack" kill was not simulated (asyncpg gives no hook
  between server COMMIT and client receipt); the blind-reapply proof is the correct empirical
  stand-in and it holds.
- Existing data fully preserved through the full chain: full-row equality on the sentinel task,
  physical row not rewritten (ctid unchanged), all six 031-added columns NULL on the legacy row (no
  backfill), pre-031 clarification columns unchanged.
- Pre-activation down (035->031) removes only the five new tables; pre-031 tables + sentinel intact;
  reapply reproduces the pre-down fingerprint exactly.
- Post-write operational rollback is non-destructive: synthetic rows in all five new tables survive
  a simulated version rollback (no down run). Old-version compatibility exercised via explicit
  pre-031 column list, `SELECT *`, and representative task/clarification read AND write.
- Advisory lock: session-level (correct — the xact-scoped variant cannot span files that each COMMIT
  internally); key is a deterministic server-side `hashtextextended(fixed_string)` (never Python
  `hash()`); acquired before any DDL; released on success, on Python exception (finally), on
  cancellation+close, and on forced backend termination (all verified).
- No secret logging: `migration_runner.py` performs no logging/printing and never receives a DSN or
  credential (it takes an already-open connection). Verified by source scan.
```

## Regression (independently re-run on both commits)

```text
baseline 18f11fe:  3 failed / 314 passed / 5 skipped   (step66c4-tagged suite)
feature  27184b5:  3 failed / 340 passed / 5 skipped   (= 314 + 12 RA-1A + 14 this review)
```

The three failures are byte-for-byte identical on both commits and none touch RA-1A migration
correctness:

```text
test_step66c4_be1_merge.py::test_no_live_outbox_producer_on_main
  -> stale BE1-M guard; fails because already-merged BE3 modules (replay/resume) reference the
     outbox. Not migration-apply related. No RA-1A bearing.
test_step66c4_be3_planning.py::test_no_backend_api_migration_frontend_deployment_code_changed
  -> BE3-P planning diff-guard vs an old ref; fails on apps/orchestrator/src/main.py changed by
     already-merged BE3. A git-diff guard, not a migration-apply test. No RA-1A bearing.
test_step66c4_be3_runtime_activation_planning.py::test_verifier_script_passes
  -> FileNotFoundError: 'python'. PATH-dependent (host has only python3). Independently evaluated:
     it invokes a DIFFERENT stage's verifier via a bare `python` subprocess; RA-1A's own verifier
     and this review's verifier both use explicit interpreters. Pre-existing environment quirk, NOT
     an RA-1 blocker, though it is a real CI-portability nit worth fixing separately.
```

No skip/xfail marker was weakened between baseline and feature for any touched test file.

## Conclusion

The isolated migration rehearsal is correct and RA-1A's specific claims re-derive. However, the
`migration_runner.py` foundation carries one High (H-1) and three Medium (M-1/M-2/M-3) findings that
each block a **future shared-apply** readiness decision. Per the review spec's PASS criteria (no High;
no Medium that blocks future shared-apply), the technical verdict is **REMEDIATION_REQUIRED**. This
verdict applies only to isolated-rehearsal correctness and shared-apply-readiness foundation; it
authorizes no shared migration, deployment, or activation.

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
