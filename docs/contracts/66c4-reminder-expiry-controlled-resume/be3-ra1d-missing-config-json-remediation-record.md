# Step 66C.4-BE3-RA-1D — Missing Configuration JSON Contract Closure

> **Remediation record. Closes the single M-3B residual from the Step 66C.4-BE3-RA-1FC2 second
> focused closure. Performed by the original RA-1A/RA-1B/RA-1C implementation session, per this
> stage's own instruction. H-1, M-1, M-2A, M-2B, and M-3A (all already CLOSED) are unmodified. NOT
> applied to any shared database. NOT deployed. NOT activated. Draft PR #21 remains Draft/OPEN/NOT
> FOR MERGE. Migrations 029-035 are UNCHANGED.**

## 1. Baseline confirmed

Before any implementation change: `origin/feature/66c4-be3-ra1-migration-rehearsal` = `7820b4b`,
`origin/review/66c4-be3-ra1-migration-rollback` = `800035b` (the RA-1FC2 second focused-closure
commit), PR #21 Draft/OPEN/unmerged, working tree clean — all confirmed per this stage's own §1.

## 2. Finding

**RA-1FC2 §17/§19:** `_dsn_from_env()` printed a plain-text line
(`f"{DSN_ENV} is not set; refusing to run."`) to stderr and called `sys.exit(2)` directly when
`PLATFORM_MIGRATIONS_DATABASE_URL` was missing — the only CLI failure path that did not follow the
single, redacted, structured-JSON contract every other path (connect failure, migration/drift
failure) already used. No secret was exposed (only the env var *name*), but the output contract
itself was inconsistent, and whitespace-only values (e.g. `"   "`) were not treated as "not
configured" at all (`not dsn` is `False` for a non-empty whitespace string) — they would have been
passed straight through to `asyncpg.connect()`, misclassifying what is really a configuration
problem as a connection failure.

## 3. Fix

`_dsn_from_env()` no longer prints anything or calls `sys.exit()` itself. It now returns
`str | None`: `None` for missing, empty, OR whitespace-only (`dsn is None or not dsn.strip()`),
otherwise the DSN unchanged. A new, single function, `_print_missing_configuration(mode)`, is the
ONLY place that ever emits the missing-configuration output — called once, from `main()`, exactly
where the plan/apply mode is already known (`mode = "plan" if args.plan else "apply"`, computed
before the DSN check):

```python
def _print_missing_configuration(mode: str) -> int:
    payload = {
        "result_code": "missing_configuration",
        "mode": mode,
        "success": False,
        "message": "Required database configuration is missing.",
        "failed_version": None,
    }
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 2
```

`main()`'s control flow:

```text
mode = "plan" if args.plan else "apply"
dsn = _dsn_from_env()
if dsn is None:
    return _print_missing_configuration(mode)   # exit 2, single JSON, nothing else
if mode == "plan":
    return asyncio.run(_run_plan(dsn))
return asyncio.run(_run_apply(dsn))
```

This satisfies every constraint in this stage's §3:

1. **Single location responsible** — `_print_missing_configuration` is the only place this output
   is produced; `_dsn_from_env` produces no output at all.
2. **No plain-text-then-JSON** — the old `print(...)` call in `_dsn_from_env` is gone entirely.
3. **No second output around `SystemExit`** — `_dsn_from_env` no longer calls `sys.exit()` at all;
   the exit code flows back through `main()`'s own `return` and the module-level
   `sys.exit(main())`, identical in shape to every other CLI exit path.
4. **Nothing beyond the env var *name*** — the env var name doesn't even appear in the output; the
   message is a fixed, generic string.
5. **No DSN/host/port/database/username/password** — the payload contains only the fixed message
   above; the actual (missing, empty, or whitespace) value of the env var is never read into the
   payload.

**Malformed-DSN misclassification, explicitly avoided:** `_dsn_from_env` only checks
presence/emptiness/whitespace — a syntactically-invalid-but-present string (e.g.
`"this-is-not-a-valid-dsn-at-all"`) is NOT `None`, so it flows through to `_connect_or_none`,
which fails at `asyncpg.connect()` and correctly lands on the EXISTING `database_connect_failed` /
exit-1 path — never misclassified as `missing_configuration` / exit-2. Verified directly (see
evidence record).

## 4. Existing contracts preserved (unmodified)

- **Successful plan/apply**: exit 0, exactly one JSON object on stdout, stderr empty — untouched
  (`_run_plan`/`_run_apply` success paths were not touched).
- **Database connection failure**: exit 1, exactly one redacted JSON object on stderr, no
  traceback — `_print_connect_failure` was not touched.
- **Migration/drift/checksum failure**: exit 1, single structured JSON result — the
  `apply_chain_with_ledger` exception-handling block in `_run_apply` was not touched.
- H-1, M-1, M-2A, M-2B, M-3A (`migration_runner.py`, the migration manifests, migrations 029-035)
  were not touched at all — this stage's entire diff is confined to
  `scripts/run_platform_migrations.py`.

## 5. Scope discipline

```text
Modified:   scripts/run_platform_migrations.py (allowed change; the only implementation file
            touched)
Added:      tests/test_step66c4_be3_ra1d_missing_config_json.py, this record, the evidence record,
            the handoff record, the self-verifier
NOT touched: migrations/029-035, shared/sdk/backup_dr/migration_runner.py, shared/sdk/backup_dr/
            migration_manifests/*, any BE3 runtime service, any feature-gate default, any
            deployment configuration, any Compose/Helm/Kubernetes runtime value, any file from the
            RA-1R/RA-1FC/RA-1FC2 review branch (review/66c4-be3-ra1-migration-rollback, up to and
            including its 800035b second focused-closure commit).
```

## Statement

Remediation record only. No shared migration application. No deployment. No feature-gate change.
No runtime validation. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
