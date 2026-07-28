# Step 66C.4-BE3-R-FC — Focused-Closure Test Evidence (M-1, L-1, R2-1)

> Independent test/verification evidence for the closure of findings M-1, L-1, R2-1 at feature head
> `5a413bf` (closure diff `6323972..5a413bf`). All execution was on an internal test runtime against
> an isolated ephemeral PostgreSQL 16 created for this closure and destroyed afterwards; the shared
> test stack was not touched. No Redis path was required by these three findings, so none was
> exercised for this stage (the one Redis-exercising path — audit-relay routing — is unaffected by
> R1/R2 and was already covered in the original BE3-R evidence).

## Environment

- Runner: internal test runtime, project Python 3.12 virtualenv, `pytest 9.0.3`, `asyncpg 0.31.0`.
- Isolated ephemeral PostgreSQL 16 (fresh `postgres:16` container on a spare loopback port; DB name
  matching the `ephemeral_*` isolated-test convention required by `tests/step66c4_pg_safety.py`).
- Detached git worktree at `5a413bf` on the internal test runtime; the reviewer's added test +
  verifier overlaid; both removed after the run.
- Shared-stack safety: the shared PostgreSQL/Redis containers had identical container IDs before and
  after this closure run (verified). No shared container was created, restarted, or mutated.

## Independent verifier

`scripts/verify_step66c4_be3_r1_r2_focused_closure.py` (static, no DB/network): all structural
invariants hold — migration 035 additive + resource/action/team/project/state-version/time-bound +
single-use + revocable + FK; the resolver FOR UPDATE-locks before checks and the consuming CAS
re-binds every predicate; `authorization_service.consume` resolves the approval before the
authorization consume and raises on a post-approval-consume authz CAS failure; grant boundary is the
canonical approver pair; no HTTP grant/revoke endpoint; L-1 uses `pg_advisory_xact_lock` +
`hashtextextended` (not Python `hash()`), keyed on team+project+actor, acquired before the dead-row
lock, with the count scoped by (team, project); R2-1 removes `production_effect` from the API schema,
derives it server-side fail-closed, folds it into the canonical `resource_state_version`, and
revalidates at request+authorize+consume; the activation gate records M-1/L-1/R2-1 while preserving
items 1-11 and the NO-deployment/NO-shared-migration/NO-activation posture.

```
STEP66C4_BE3_R1_R2_FOCUSED_CLOSURE_VERIFY: PASS
```

## Mandatory suites — 0 failed / 0 skipped

| Suite | Result |
|---|---|
| `tests/test_step66c4_be3_r1_r2_focused_closure.py` (independent, this closure) | 22 passed, 0 skipped |
| `tests/test_step66c4_be3_r1_findings_remediation.py` | included in **140 passed, 0 skipped** |
| `tests/test_step66c4_be3_r2_resume_production_effect.py` | (same run) |
| `tests/test_step66c4_be3_a_authorization_foundation.py` | (same run) |
| `tests/test_step66c4_be3_b_operator_resume.py` | (same run) |
| `tests/test_step66c4_be3_c_authorized_replay.py` | (same run) |
| `tests/test_step66c4_be3_b_c1_authority_routing_alignment.py` | (same run) |
| BE1/BE2 regression (`be1_data_model`, `be1_r1`, `be2_r1`) | 75 passed, 0 skipped |

The 140-test mandatory run was repeated on the final black-reformatted bytes of the reviewer's added
files; still 140 passed / 0 skipped.

## Independent test → closure-requirement mapping

| Independent test | Requirement re-derived |
|---|---|
| `test_m1_valid_approval_allows_production_consume_and_marks_consumed` | M-1 §6 valid approval → allowed, consumed once, traced to the authorization |
| `test_m1_every_invalid_reference_blocks_and_leaves_unconsumed` | M-1 §6 missing/invalid/unknown/revoked/expired/consumed/wrong-action/wrong-resource/wrong-scope/stale → blocked, unconsumed |
| `test_m1_post_approval_consume_authz_failure_rolls_back_both` | M-1 §6 authz CAS failure after approval consume → full rollback |
| `test_m1_no_toctou_concurrent_revoke_vs_consume` | M-1 §6 lock/read → no TOCTOU (exactly one of consume/revoke) |
| `test_m1_replay_execute_outbox_failure_rolls_back_approval_and_dead_row` | M-1 §6 outbox/audit failure → authz + approval unconsumed, no replay mutation |
| `test_m1_grant_boundary_is_approver_only` / `test_m1_can_grant_is_canonical_approver_pair` | M-1 §5 grant boundary; Service Identity / Operator cannot grant |
| `test_l1_uses_pg_advisory_lock_not_python_hash` | L-1 §7 pg advisory lock, server-side hash, not Python hash() |
| `test_l1_20_concurrent_requests_cap_10_exactly_10` | L-1 §8 20 concurrent, cap 10 → exactly 10 |
| `test_l1_50_concurrent_requests_cap_3_never_exceeds` | L-1 §8 50 concurrent, cap 3 → ≤3 |
| `test_l1_caps_are_isolated_per_team_project_actor` | L-1 §8 independent caps per team/project |
| `test_l1_idempotency_concurrency_yields_one_row` | L-1 §8 same idempotency key → one durable row |
| `test_l1_advisory_lock_released_after_rollback` | L-1 §7 xact lock released on rollback (no session leak) |
| `test_l1_platform_admin_cannot_bypass_and_invalid_config_fails_closed` | L-1 §8 admin no bypass; invalid config fails closed |
| `test_l1_rolling_window_excludes_old_requests` | L-1 §8 requests outside 24h window not counted |
| `test_l1_per_event_successful_replay_cap_still_holds` | L-1 §8 per-event 3-success cap unchanged |
| `test_r2_api_schema_has_no_production_effect_field` | R2-1 §10 client cannot send production_effect |
| `test_r2_state_version_includes_production_effect` | R2-1 §11 production_effect in canonical state version, fail-closed |
| `test_r2_client_cannot_downgrade_production_task` | R2-1 §10 production task → production authorization |
| `test_r2_client_cannot_upgrade_nonproduction_task` | R2-1 §10 non-production task stays non-production |
| `test_r2_task_classification_change_invalidates_outstanding_request` | R2-1 §11 classification flip → stale_state, no side effect |
| `test_r2_scope_isolation_and_task_mismatch` | R2-1 §12 cross-project → not_found_masked; NULL scope → fail closed |

## Positive behavioural-inversion confirmation (M-1)

The original BE3-R combined-review finding-DEMONSTRATION test
(`tests/test_step66c4_be3_combined_review.py::test_production_approval_reference_is_only_nonempty_checked`),
which asserted the PRE-fix behaviour, was run UNCHANGED against `5a413bf`: it now FAILS (the bogus
reference is rejected as `production_approval_invalid_reference`), which positively confirms M-1 is
closed. The other four finding-related combined-review tests (dead-episode version, one-active-
request-per-event, destination-not-ready, replay-execution rollback) still pass. The historical test
was NOT modified or weakened (append-only).

## Quality gates (reviewer's changed files)

`ruff check`, `black --check`, `mypy` all clean on
`tests/test_step66c4_be3_r1_r2_focused_closure.py` and
`scripts/verify_step66c4_be3_r1_r2_focused_closure.py`; `git diff --check` clean; secret/internal-
identifier scan clean (no internal IP / SSH alias / hostname / username / private key in any
committed artifact — the verifier hardcodes no private literal).

## Safety

Shared migration applied — NO. Deployment — NO. Feature activation — NO. Runtime resume/replay — NO.
PR #20 merged — NO. `production_executed_true_count` — 0. Ephemeral PostgreSQL 16 destroyed after;
shared stack container IDs identical before/after.

---
_Non-production only. No production action. No internal IP addresses, SSH aliases, private
hostnames, usernames, or credentials appear in this record — only neutral labels._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
