# Step 66C.4-BE3-RA-1FC — Focused Closure Review (H-1 / M-1 / M-2 / M-3)

> **Independent focused-closure review by the ORIGINAL RA-1R reviewer (continuity), NOT the RA-1B
> implementation session. Scope is EXACTLY H-1/M-1/M-2/M-3 — no re-run of the full RA-1 architecture
> review; L-1/L-2 are out of scope. Every conclusion is re-derived from the committed
> `migration_runner.py` (b31e655), the CLI, and direct experiments against an isolated ephemeral
> PostgreSQL 16 — not from RA-1B's own self-verifier. This review authorizes NO shared migration, NO
> deployment, NO activation, NO merge; it modifies no implementation file.**

## Markers (never conflated)

```text
Process marker (artifacts/process complete): STEP66C4_BE3_RA1B_FOCUSED_CLOSURE_VERIFY: PASS
Technical verdict (independent judgment):     RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

## Per-finding verdict

```text
H-1  Failure-path rollback / unlock / connection disposal ...... CLOSED
M-1  Semantic schema-fingerprint completeness .................. CLOSED
M-2  Migration ledger and provenance ........................... REMEDIATION_REQUIRED
M-3  Bounded waits and operational controls .................... REMEDIATION_REQUIRED
```

Two of the four findings are strongly and completely closed; two are substantially implemented but
each retains a concrete, empirically-demonstrated gap. Because M-2 and M-3 are not fully closed, and
per the closure spec the overall verdict may be PASS only if ALL of H-1/M-1/M-2/M-3 are closed (and
`ledger/down inconsistency` and `secret leakage` may never be closed as PASS_WITH_GAPS), the overall
technical verdict is **REMEDIATION_REQUIRED**.

## Scope reviewed

```text
Canonical main:              18f11fe
Reviewed RA-1A head:         27184b5
Reviewed RA-1B remediation:  b31e655   (PR #21 Draft/OPEN/unmerged — confirmed before and after)
Original review commit:      352d546   (preserved, unmodified)
Reviewer-only integration:   19cff82   (merge of b31e655 into the review branch; NOT FOR MAIN, no PR)
Focused remediation diff:    27184b5..b31e655  (migration_runner.py +732; new CLI; +23 tests;
                             two BE1 allowlist guards touched; migrations 029-035 UNCHANGED)
```

All PostgreSQL work ran on an isolated ephemeral PostgreSQL 16.14 container on an internal test
runtime (distinct container name and port from every prior RA-1 stage), destroyed after the review.

---

## H-1 — CLOSED

The cleanup order is now correct and empirically verified: **capture original error → ROLLBACK →
advisory unlock → (restore session timeouts, in the ledger path) → re-raise the ORIGINAL error**.
Each cleanup step runs through `_safe_cleanup_step` (`asyncio.wait_for` + `asyncio.shield`, bounded
at 10 s, catching `BaseException`), which never raises — it returns the exception, so a cleanup
failure can never replace the original error.

Independently reproduced (my `test_h1_*`):

```text
mid-file failure -> propagated exception is the ORIGINAL asyncpg DivisionByZeroError (NOT masked);
                    .ra1b_cleanup_errors == []; .ra1b_connection_reusable is True; ROLLBACK ran
                    before unlock so the SAME connection is immediately reusable (SELECT 1 works);
                    the advisory lock is released (a fresh connection acquires it); no partial object.
forced backend termination mid-migration (admin pg_terminate_backend) -> the runner's own ROLLBACK
                    step fails; .ra1b_connection_reusable is False and the runner CLOSES the
                    connection (conn.is_closed() is True) rather than handing back a poisoned one.
cancellation while holding the lock -> the lock is released and CancelledError ultimately propagates.
real asyncpg.Pool (max_size=1): a failed migration then release/acquire -> the next borrower gets a
                    clean, idle connection with NO leaked advisory lock (SELECT 1 works, lock free).
```

The `.ra1b_*` attribute-attach concern (spec §4: fail safely if an exception forbids dynamic
attributes) was checked against every reachable exception type — `ZeroDivisionError`,
`CancelledError`, `asyncpg.PostgresError`, `MigrationLockTimeoutError`, `SchemaDriftError`,
`TimeoutError`, `KeyboardInterrupt` — all accept the attribute, so the attach can never itself raise
a new masking error in practice. (The code still lacks a defensive guard around the assignment; since
no reachable type disallows it, this is at most a hardening nicety, not a defect — noted, not
blocking.)

---

## M-1 — CLOSED

`schema_fingerprint` now reads constraints via `pg_get_constraintdef(con.oid)` (plus explicit
`condeferrable`/`condeferred`/`convalidated`) and indexes via `indexdef` + `am.amname`. All eleven
mutation categories the closure spec (§8) enumerates are independently detected — including the
three RA-1B's own suite never tested:

```text
same-name CHECK expression change ......... DETECTED
FK ON DELETE change ....................... DETECTED
FK ON UPDATE change ....................... DETECTED
FK MATCH change (SIMPLE -> FULL) .......... DETECTED   (untested by RA-1B)
FK deferrability change ................... DETECTED
constraint validation-state (NOT VALID->valid) DETECTED   (untested by RA-1B)
partial-index predicate change ............ DETECTED
index expression change ................... DETECTED
index access-method change (btree->hash) .. DETECTED   (untested by RA-1B)
column default change ..................... DETECTED
nullability change ........................ DETECTED (round-trip returns to identical fingerprint)
```

Fingerprint is deterministic across recomputation; the OID-embedded NOT NULL pseudo-constraint
exclusion loses no semantics (nullability is captured via `information_schema.columns.is_nullable`,
confirmed by the round-trip). No gap.

---

## M-2 — REMEDIATION_REQUIRED

The ledger (`platform_schema_migrations`) is a genuine, well-shaped provenance mechanism and most of
its behavior is correct and independently verified:

```text
ledger bootstrap under the chain lock; per-version applied status + correct SHA-256 .... OK
duplicate invocation -> ledger fast-path skip (no re-execution) ......................... OK
checksum mismatch on an applied version -> MigrationChecksumMismatchError, row NOT overwritten  OK
target table exists with no ledger row -> UntrackedSchemaError (never auto-adopted) ..... OK
applying row with NO matching object -> SchemaDriftError (fail closed) .................. OK
genuine ambiguous commit (real DDL + applying row) -> reconciled_after_ambiguous_commit . OK
wrong-shaped ledger table -> fails closed (loud error, does not proceed) ................ OK
029/030 baseline boundary: ledger governs only 031+; 029/030 are not mis-flagged as illegal for
  lacking a ledger row; unknown-origin 031-035 objects are NOT trusted (UntrackedSchemaError) . OK
```

But two concrete gaps remain, both empirically demonstrated:

### M-2 gap A (blocking, spec §13) — no consistent ledger vs. down / reapply strategy

After a ledger-aware apply of 031-035, running the pre-activation down scripts (the exact
raw-`conn.execute(down_sql)` path RA-1A rehearses) leaves the ledger and the schema **incoherent**,
and neither a ledger-aware down (resolution A) nor a documented fail-closed exclusion (resolution B)
exists. Reproduced (`test_m2_GAP_down_then_reapply_lifecycle_is_inconsistent`):

```text
after down: all five target tables are GONE, but every ledger row still says status='applied'.
plan_chain: drift_status = {031..035: 'ok'}, schema_state = {031..035: False},
            pending_versions = [], current_version = '035'
            -> plan does NOT fail closed on the ledger-vs-schema mismatch; it reports a clean,
               fully-applied state while the schema is entirely absent.
reapply (apply_chain_with_ledger): result_code='success', applied=[], reconciled=[]
            -> it SILENTLY SKIPS every migration (ledger says applied) and DOES NOT recreate the
               dropped tables, while reporting success.
```

The closure spec §13 requires an explicit answer to exactly this scenario and states plainly: *"若
ledger 與 down/reapply 無一致策略，M-2 不得關閉."* The current behavior lands squarely on the spec's
**unacceptable** list ("blindly reapply", "silently … as applied"): a reapply reports success while
the schema is missing, and plan neither flags nor fails closed. The RA-1B remediation record and
evidence are silent on the down/reapply lifecycle (they document only the apply-side ledger states).
This gap alone prevents M-2 closure.

Acceptable remediations (per §13): either make down a ledger-aware, lock-protected, auditable state
transition (A); or explicitly document that destructive down is NOT part of the ledger-managed apply
workflow, restrict pre-activation down to isolated rehearsal, adopt application-rollback + table
retention for shared rollback, AND make `plan_chain` fail closed with a clear diagnostic when a
version is ledger-`applied` but its schema is absent (B). Today neither holds.

### M-2 gap B (blocking, spec §12) — ambiguous-commit reconcile accepts a wrong-shaped table

`§12` requires that an `applying` row reconcile ONLY when version, filename, checksum, **expected
fingerprint, and observed fingerprint** all match, else fail closed / mark drifted. In the
implementation an `applying` row's `expected_fingerprint` is **never populated** (only `_mark_applied`
and `_mark_reconciled` set fingerprints, both AFTER the fact), so the expected-fingerprint criterion
is vacuous, and reconcile completeness checks only table **existence**, not shape. Reproduced
(`test_m2_GAP_reconcile_accepts_wrong_shaped_table`):

```text
applying row with the REAL 032 checksum + the 032 table present but ALTERED (extra rogue column)
  -> apply_chain_with_ledger RECONCILES it (reconciled_versions == ['032']); the wrong shape is
     accepted, not flagged as drift.
```

So a drifted/tampered target that merely exists under an `applying` row with a matching checksum is
adopted as reconciled. This weakens the very provenance guarantee M-2 exists to provide. (A stored
golden/expected fingerprint per migration, compared at reconcile time, would close it.)

---

## M-3 — REMEDIATION_REQUIRED

The core operational controls are implemented and independently verified:

```text
bounded advisory-lock wait (pg_try_advisory_lock polled to a monotonic deadline): a held lock ->
  MigrationLockTimeoutError within the window (~1 s for a 1 s deadline), no lock taken/left; release
  then reapply succeeds ................................................................. OK
invalid timeout/poll/statement config -> MigrationConfigError (fails closed, never clamped) . OK
statement_timeout/lock_timeout/idle_in_transaction_session_timeout set then restored to prior
  exact values after a successful run .................................................. OK
plan_chain is read-only: creates neither the ledger nor any target table across all five schema
  states (empty / pre-031 / partial / untracked / fully-applied); reports pending/current/checksums/
  drift/untracked correctly ............................................................. OK
CLI exit codes: --plan and --apply exit 0 with a single JSON object on stdout; missing DSN exits 2 . OK
```

Gap (spec §16/§18) — incomplete redaction and an unstructured connect-failure path:

```text
redact_for_operator("postgresql://user:hunter2pw@host/db")  -> returned UNREDACTED (leaks the string)
redact_for_operator("postgres://user:hunter2pw@host/db")    -> "[redacted ...]"  (only this variant)
redact_for_operator("password authentication failed")       -> "[redacted ...]"
```

The redactor's marker list contains `postgres://` but NOT the canonical asyncpg `postgresql://`
scheme, so the most common DSN form passes through unredacted. Separately, the CLI's
`asyncpg.connect(dsn=…)` is OUTSIDE the redacting `try`, so a connect failure (e.g. a wrong DSN —
a routine operator error) prints a **raw Python traceback** to stderr with exit 1, not the redacted
single-JSON object §18 requires.

Severity, stated precisely: I did **not** demonstrate a credential-VALUE leak in a reachable path —
asyncpg's `InvalidPasswordError` message is `password authentication failed for user "…"` and does
not echo the password value, and migration SQL errors do not contain the DSN. So this is a
redaction-**completeness** defect plus a §18 output-contract violation on the connect-failure path,
not a demonstrated secret disclosure. But the redactor is the named secret-safety control and it
provably fails on the standard DSN scheme; because the closure spec forbids closing over any
`secret leakage` / incomplete secret control as PASS_WITH_GAPS, and §18 requires redacted single-JSON
output on all CLI paths, M-3 cannot be marked closed until the redactor covers `postgresql://` (and
the CLI wraps connect failures in the same redacted structured result).

### Allowlist guard-test review (spec §19)

The two BE1/BE1-R1 outbox-producer guards each added exactly **one precise file-path literal**
(`shared/sdk/backup_dr/migration_runner.py`) to their `allowed` set — no wildcard, glob, regex, or
directory-level exemption inside the set (verified by isolating the `allowed = {…}` literal). Both
guards still fail closed for any other unlisted module that references the outbox, and both PASS on
b31e655 (confirmed in regression). Note: the closure spec §19's example negative cases
(`platform_schema_migrations_backup`, `production_schema_migrations`, `DROP TABLE …`) presume a
SQL/table-name-pattern allowlist; the actual guards are FILE-PATH allowlists for outbox-producer
references, so those literal cases do not apply — but the substantive requirement (precise addition,
no broadening, forbidden references still caught) is met.

---

## Regression (independently re-run on both commits)

```text
baseline 18f11fe:  3 failed / 314 passed / 5 skipped   (step66c4-tagged)
feature  b31e655:  3 failed / 369 passed / 5 skipped   (= 314 + 12 RA-1A + 23 RA-1B + 20 this closure)
```

The three failures are the SAME pre-existing ones identified in RA-1R, identical node IDs on both
commits, none migration/backup/CLI-related, none introduced by RA-1B:

```text
test_step66c4_be1_merge.py::test_no_live_outbox_producer_on_main .................... pre-existing
test_step66c4_be3_planning.py::test_no_backend_api_migration_frontend_deployment_code_changed  pre-existing
test_step66c4_be3_runtime_activation_planning.py::test_verifier_script_passes (bare `python`)  pre-existing
```

No new feature-only failure, no additional skip (5 on both), no assertion weakened; the two BE1
allowlist guards PASS on feature (RA-1B's ledger-string reference did not regress them). Directly
affected RA-1 suites (RA-1A rehearsal + RA-1B remediation + this closure) together: **55 passed / 0
failed / 0 skipped**.

## Conclusion

H-1 and M-1 are independently confirmed CLOSED. M-2 and M-3 are substantially implemented but each
retains a concrete, reproduced gap: M-2's ledger has no coherent story for down/reapply (plan does
not fail closed on a ledger-vs-schema mismatch; reapply falsely reports success while the schema is
absent) and reconciles a wrong-shaped table; M-3's redaction control misses the canonical
`postgresql://` DSN scheme and the CLI's connect-failure path is an unredacted raw traceback. Per the
closure spec's own gating (all four must be closed; ledger/down inconsistency and secret-control
gaps may not be closed as PASS_WITH_GAPS), the technical verdict is **REMEDIATION_REQUIRED**. This
verdict applies only to migration-runner shared-apply readiness; it authorizes no shared migration,
deployment, or activation.

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
