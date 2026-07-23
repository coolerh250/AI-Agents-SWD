# Step 66C.4-BE2-R — Test Quality & Historical-Guard Review

> **Independent review. Reviewer did not implement the code. Evidence gathered on an isolated
> ephemeral PostgreSQL 16 + Redis 7 stack on the internal test runtime. Nothing deployed.**

Reviewed commit: `319123b`.

## 14. Historical test modification — PASS (guard not weakened)

BE2 modified three prior zero-live-producer guard tests:
`tests/test_step66c4_be1_data_model_deadline_outbox.py`,
`tests/test_step66c4_be1_merge.py`, `tests/test_step66c4_be1_r1_remediation.py`.

Each change replaces a single-file exclusion (`lifecycle_outbox.py`) with an explicit `allowed` set of
**exactly three specific paths**: `lifecycle_outbox.py`, `lifecycle_poller.py`, `outbox_relay.py`.
Assessment against the §14 checklist:

1. Original BE1/R1 historical evidence intact — YES. The prior commits (BE1 data-model, BE1 merge,
   BE1-R1 remediation) are unchanged in history; only the guard's allowlist was widened, with a
   comment.
2. Allows ONLY the two authorized non-activated worker modules (plus the pre-existing outbox module)
   — YES, exact file paths.
3. No broad glob / whole-package allowlist — YES; it is a set of three concrete paths, not a directory
   or prefix.
4. Any OTHER runtime caller still fails — YES; any non-allowlisted `apps/**` or `shared/**` module
   that references `lifecycle_outbox` / `clarification_lifecycle_outbox` still lands in `offenders`
   and fails the assertion.
5. Startup registration still fails — covered by the NEW BE2 test
   `test_no_startup_background_task_on_import` (no module-level `create_task`/`run`).
6. Deployment/compose activation still fails — covered by the NEW BE2 test
   `test_entrypoints_not_registered_in_any_compose_or_workflow`, which scans
   `infra/helm/k8s/.github/workflows` for the worker names/modules.
7. Clear stage-transition comment/record — YES ("Updated in BE2 (PO-authorized)…").
8. Did NOT turn "no live producer" into "allow any producer" — YES; the guard still fails for any
   producer outside the three named modules.

I re-ran the three modified suites against the ephemeral stack: **69 passed**. The historical safety
invariant is preserved.

## 18. Regression & quality

- Vendor BE2 suite `tests/test_step66c4_be2_reminder_expiry_outbox_relay.py`: **28 passed, 0 skipped**
  against the ephemeral PG16 + Redis 7 stack.
- Vendor verifier `scripts/verify_step66c4_be2_reminder_expiry_outbox_relay.py`: exit 0, prints
  `STEP66C4_BE2_REMINDER_EXPIRY_OUTBOX_RELAY_VERIFY: PASS` (self-verification only).
- BE1 regression (data-model, merge, R1 remediation): **69 passed**.
- Audit/retry/workroom regression sample (`test_audit_normalizer`, `test_audit_worker`,
  `test_deadletter_foundation`, `test_retry_dlq_validation`, `test_step66c1_workroom_clarification_api`):
  **52 passed, 3 skipped** — the 3 skips are pre-existing environment-gated tests, not BE2-caused.
- `ruff check` on the five affected implementation files: clean.
- `black --check` on the five affected files: clean (would be left unchanged).
- `mypy` on the three `shared/sdk/tasks` modules: `Success: no issues found`.
- `git diff --check origin/main...HEAD`: clean.

No regression attributable to BE2. Repo-wide pre-existing skips are recorded separately above and are
NOT counted against BE2.

## Test-coverage gap (feeds §6.3)

The vendor test `test_pg_expiry_skips_answered_and_canceled_and_protects_terminal_task` asserts the
protected-terminal-task behavior but **does not assert the outbox count** for that clarification, so
it masks the fact that a `clarification.expired` row is still committed for a task that never
transitioned. There is also **no test** for a legal-but-unexpected NON-terminal task state during
expiry. My independent reproductions filled both gaps (see the lifecycle-poller and
transaction-and-concurrency reviews).

## Mandatory-test result

Poller + relay + destination mandatory reproductions (§17): **0 failed, 0 mandatory skipped** across
the vendor suite and my own independent scripts.

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
