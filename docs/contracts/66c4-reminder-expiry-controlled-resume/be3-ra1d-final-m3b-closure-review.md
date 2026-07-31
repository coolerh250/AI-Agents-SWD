# Step 66C.4-BE3-RA-1FC3 — Final M-3B CLI-Contract Closure Review

> **Independent third and final focused-closure review by the ORIGINAL RA-1R / RA-1FC / RA-1FC2
> reviewer (continuity), NOT the RA-1D implementation session. Scope is EXACTLY the one M-3B residual
> — the missing-configuration CLI must follow the single-JSON error contract. No re-run of the full
> RA-1 review. Every conclusion is re-derived from the committed `run_platform_migrations.py`
> (97e56d4) and direct subprocess experiments against a fresh isolated ephemeral PostgreSQL 16 — not
> from RA-1D's own self-verifier. Authorizes NO shared migration, NO deployment, NO activation, NO
> merge; modifies no implementation file or test under review.**

## Markers (never conflated)

```text
Process marker (artifacts/process complete): STEP66C4_BE3_RA1D_FINAL_M3B_CLOSURE_VERIFY: PASS
Technical verdict (independent judgment):     RA1_TECHNICAL_VERDICT: PASS
```

The single M-3B residual carried by the RA-1FC2 verdict is now closed, no new blocking finding was
introduced, and the H-1/M-1/M-2/M-3A behaviors are untouched (byte-identical runner/manifests/
migrations). All four RA-1 findings (H-1, M-1, M-2, M-3) plus their focused-closure residuals are now
independently verified closed.

## Per-finding verdict

```text
M-3B  Missing / empty / whitespace-only configuration follows the single-JSON CLI contract ... CLOSED
```

## Scope reviewed

```text
Canonical main:                18f11fe
RA-1C head (prior residual):   7820b4b
RA-1D remediation head:        97e56d4   (PR #21 Draft/OPEN/unmerged — confirmed before and after)
Prior review head:             800035b   (RA-1FC2; preserved, unmodified)
Reviewer-only integration:     7c6b830   (merge of 97e56d4 into the review branch; NOT FOR MAIN)
Focused remediation diff:      7820b4b..97e56d4  (run_platform_migrations.py +30/-5; docs; RA-1D
                               verifier + 12-test suite; migrations/manifests/runner UNCHANGED)
```

All PostgreSQL work ran on a fresh isolated ephemeral PostgreSQL 16.14 container on an internal test
runtime (distinct container name and port from every prior RA-1 stage), destroyed after the review.

## Diff-scope verification (§3) — independently confirmed

The change is confined to the CLI and its new tests/docs. I confirmed by direct `git diff`:

```text
byte-identical to 7820b4b:  shared/sdk/backup_dr/migration_runner.py       (empty diff)
                            shared/sdk/backup_dr/migration_manifests/*      (empty diff)
                            migrations/029*..035* (all forward + down)      (empty diff)
only implementation file changed:  scripts/run_platform_migrations.py
```

Therefore H-1 cleanup behavior, M-1 fingerprint behavior, M-2 ledger/schema consistency, M-2 manifest
provenance, and M-3A DSN redaction are all in unchanged code, and no feature-gate default or
deployment configuration is touched. No implementation change outside the CLI missing-config scope
was found. The CLI diff itself is limited to: `_dsn_from_env` now returns `str | None` (missing/
empty/whitespace-only → `None`, via `not dsn.strip()`, no longer printing or exiting itself); a new
`_print_missing_configuration(mode)` that emits one JSON object and returns 2; and `main()` computing
`mode` up front and dispatching to it when the DSN is `None`. The connect-failure, success, and
redaction paths are unchanged.

## M-3B — CLOSED

Independently re-derived by driving the real CLI as a subprocess (my `test_step66c4_be3_ra1d_final_
m3b_closure.py`, 21 tests, 0 skipped):

### §4 — missing configuration (absent / empty / whitespace-only) × --plan / --apply

For every case (I tested five DSN-unset variants — absent, `""`, spaces, tab, mixed whitespace — ×
both modes, ten cases in total, a superset of the mandated six):

```text
exit code == 2
stdout == "" (completely empty)
stderr parses as EXACTLY one JSON object (json.loads over the FULL stderr; a plain-text prefix/suffix
  or a second document would raise) with no "Traceback"
payload == {
  "result_code": "missing_configuration",
  "mode": "plan" | "apply",           # correctly reflects the flag
  "success": false,                    # JSON boolean false (Python `is False`)
  "message": "Required database configuration is missing.",
  "failed_version": null
}
```

### §5 — JSON contract precision

stderr contains exactly one JSON document and nothing after it (proved by a clean `json.loads` of the
entire stderr string); stdout is entirely empty; `result_code` is the stable literal
`missing_configuration`; `success` is a boolean `false`; `failed_version` is `null`; `mode` is
correct. No plain-text line precedes or follows the JSON, no second JSON object, no raw `SystemExit`
message, no Python traceback, no logging prefix, no warning on stdout/stderr.

### §6 — configuration classification (no cross-contamination)

```text
missing (absent / "" / whitespace-only)            -> exit 2, result_code=missing_configuration
malformed DSN (syntactically invalid, non-empty)   -> exit 1, result_code=database_connect_failed
unreachable DSN (valid-looking but unreachable)     -> exit 1, result_code=database_connect_failed
```

A malformed or unreachable DSN is never misclassified as missing configuration, and vice versa
(verified for both modes). The `not dsn.strip()` check correctly treats only absent/empty/whitespace
as missing; a non-empty DSN always proceeds to the connect path.

### §7 — secret and endpoint safety

The missing-configuration message is a fixed, generic operator-safe string. I asserted none of the
following ever appears in stdout/stderr for the missing-config path: the environment-variable name
(`PLATFORM_MIGRATIONS_DATABASE_URL`), or fabricated username/password/host/database sentinels; and no
traceback. The unreachable-DSN path likewise leaks no username/password/host/database and no
traceback (the CLI's connect-failure path deliberately omits the exception text entirely).

### §9 — third-party logging

Re-run under `PYTHONASYNCIODEBUG=1` (+ `PYTHONWARNINGS=default`) for both a missing-config case and a
connect-failure case: stderr remains exactly one JSON object; asyncpg/asyncio/root logger inject no
second line or raw connection detail into operator stdout/stderr.

## §8 — existing CLI contracts preserved (regression)

```text
successful --plan:  exit 0, stdout = exactly one JSON object (result_code=success), stderr empty
successful --apply: exit 0, stdout = exactly one JSON object (applied_versions == [031..035]), stderr empty
connect failure:    exit 1, stdout empty, stderr = exactly one JSON object (database_connect_failed),
                    no traceback, no secret
drift/migration failure (raw-dropped owned table after a ledger apply): exit 1, stdout empty, stderr =
                    exactly one JSON object (result_code=ledger_schema_mismatch), no traceback, DSN not echoed
```

Additional independent confirmation: my prior RA-1FC2 characterization suite, re-run against 97e56d4,
is 15 passed / 1 failed — and the single failure is precisely `test_m3b_missing_config_exit_2`, which
asserted the OLD plain-text behavior (`is_json is False`). Its flip to JSON is the exact residual now
fixed; every other RA-1FC2 assertion (M-2A/M-2B/M-3A/connect/success) still passes, confirming the
change is confined to the missing-config path.

## Test integrity (§10) — RA-1D suite

The RA-1D suite (`tests/test_step66c4_be3_ra1d_missing_config_json.py`, 12 tests) is sound and not
weakened:

```text
test_cli_missing_env_exits_2_one_json[plan/apply]        env unset          exit 2, stdout=="", json.loads(stderr) one object, result_code=missing_configuration
test_cli_empty_env_exits_2_one_json[plan/apply]          env ""             (same contract)
test_cli_whitespace_only_env_exits_2_one_json[plan/apply] env "   \t  "     (same contract)
test_cli_malformed_dsn_still_exits_1_not_2[plan/apply]    malformed DSN      exit 1, database_connect_failed, DSN not echoed
test_cli_unreachable_dsn_still_exits_1_not_2[plan/apply]  unreachable DSN    exit 1, database_connect_failed, no secret
test_cli_plan_success_still_exits_0_one_stdout_json       real DB (requires_pg)  exit 0, stderr=="", stdout one JSON success
test_cli_apply_success_still_exits_0_one_stdout_json      real DB (requires_pg)  exit 0, stderr=="", applied_versions==[031..035]
```

Exactly-one-JSON is genuinely enforced — the suite calls `json.loads(result.stderr)` over the WHOLE
stderr string (a relaxed "contains JSON"/substring check would not catch a plain-text prefix; this
does). No xfail, no unconditional skip (only the two real-DB success tests carry the shared
`requires_pg` guard, which did not skip in this run), no broad exception swallowing, no ignored
subprocess output, no relaxed assertion. §10 passes.

## Regression (§12, independently re-run on both commits)

```text
baseline 18f11fe:  3 failed / 314 passed / 5 skipped   (step66c4-tagged)
feature  97e56d4:  3 failed / 413 passed / 5 skipped   (= 314 + 12 RA-1A + 23 RA-1B + 31 RA-1C + 12 RA-1D + 21 this)
```

Same three pre-existing failures (identical node IDs, unchanged signatures: the stale BE1-M and
BE3-P historical guards, and the PATH-dependent bare-`python` verifier subprocess — run here with the
repo's own venv interpreter, not bare `python`), none CLI/migration/backup-related, none introduced by
RA-1D. No new feature-only failure, no additional skip (5 on both), no assertion weakened; both BE1
allowlist guards PASS on feature. Directly affected RA-1 suites (RA-1A + RA-1B + RA-1C + RA-1D + this
closure): **99 passed / 0 failed / 0 skipped**.

## Conclusion

The RA-1FC2 M-3B residual is fully and independently closed: missing/empty/whitespace-only database
configuration now follows the same single-JSON CLI error contract as every other failure path (exit
2, `result_code=missing_configuration`, exactly one JSON object, correct mode, no plain-text/traceback/
secret), while the malformed/unreachable classification (exit 1, `database_connect_failed`), the
success paths (exit 0, single stdout JSON), and the drift path (exit 1, single stderr JSON) are all
preserved. The change is confined to the CLI; the runner, manifests, and migrations are byte-identical
to 7820b4b, so H-1/M-1/M-2/M-3A remain closed. No new blocking finding. **Technical verdict: PASS.**

This verdict certifies the RA-1 migration-runner readiness FOUNDATION as independently verified. It
does NOT authorize any shared migration, deployment, feature-gate change, or runtime activation — the
final status of Gates 1/2/6 is the PM/PO's determination per the canonical gate definition, and PR
#21 remains Draft/OPEN/unmerged.

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
