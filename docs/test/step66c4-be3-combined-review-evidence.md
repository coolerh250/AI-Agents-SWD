# Step 66C.4-BE3-R — Combined Review Test Evidence

> Independent test/verification evidence for the combined BE3-A+B+C review at feature head
> `6323972`. All execution was on an internal test runtime against an isolated ephemeral
> PostgreSQL 16 and an isolated ephemeral Redis 7, both created for this review and destroyed
> afterwards. The shared test stack was not touched.

## Environment

- Reviewed feature head: `6323972`; baseline `5745ab7`; review diff `5745ab7..6323972`.
- Runner: internal test runtime, project Python 3.12 virtualenv, `pytest 9.0.3`, `asyncpg 0.31.0`.
- Isolated ephemeral PostgreSQL 16 on a spare loopback port (fresh `postgres:16` container, DB name
  matching the `ephemeral_*` isolated-test convention required by the fail-closed destructive-PG
  guard `tests/step66c4_pg_safety.py`).
- Isolated ephemeral Redis 7 on a spare loopback port (fresh `redis:7` container) for the audit-
  relay routing test.
- Detached git worktree at `6323972` on the internal test runtime; the review's added test +
  verifier overlaid on top. Both ephemeral containers and the detached worktree were removed after
  the run.
- Shared-stack safety: the shared PostgreSQL/Redis containers had identical container IDs before and
  after the review run (verified). No shared container was created, restarted, or mutated.

## Mandatory reproduced suites (0 failed / 0 skipped for the review-relevant suites)

| Suite | Result |
|---|---|
| `tests/test_step66c4_be3_a_authorization_foundation.py` | included in **87 passed, 0 skipped** |
| `tests/test_step66c4_be3_b_operator_resume.py` | (same run) |
| `tests/test_step66c4_be3_c_authorized_replay.py` | (same run) |
| `tests/test_step66c4_be3_b_c1_authority_routing_alignment.py` | (same run) |
| `tests/test_step66c4_be1_data_model_deadline_outbox.py` + `..._be1_r1_remediation.py` + `..._be2_r1_remediation.py` | **75 passed, 0 skipped** |
| `tests/test_step66c4_be3_combined_review.py` (independent, this review) | **16 passed, 0 skipped** |

No historical BE1/BE2/BE3 verifier or test was weakened to obtain a pass.

## Independent verifier

`scripts/verify_step66c4_be3_combined_review.py` (static, no DB/network): all structural invariants
hold — additive migrations; UUID NOT NULL scope; null-safe scope predicate; single-use state-version
+ expiry-guarded consume CAS; canonical TASK_ROLES reuse; policy-authority-only resume authorization;
constant-time capability compare from a dedicated header with no logging path; total fail-closed
destination classification; audit relay restricted to audit destinations; **no public replay
execute/replay-now route (5 route decorators only)**; gates default false env-only; PG-time `dead_at`;
attempts preserved on replay; not_configured default readiness; and a secret/internal-identifier scan
of the reviewer's own committed artifacts (self-clean).

```
STEP66C4_BE3_COMBINED_INDEPENDENT_REVIEW_VERIFY: PASS
```

## Independent test coverage → review requirement mapping

| Independent test | Requirement re-derived |
|---|---|
| `test_concurrent_consume_yields_exactly_one_db_transition` | A — concurrent consume, exactly one DB transition (8-way) |
| `test_null_and_cross_scope_direct_repo_calls_isolate` | B — NULL/cross-scope direct repo calls read/affect nothing |
| `test_consume_rollback_leaves_authorization_unconsumed` | A — consume rollback restores unconsumed state |
| `test_expired_and_revoked_and_stale_never_consume` | A — expired/revoked/stale never consume |
| `test_replay_two_person_db_constraint_blocks_self_approval` | C — two-person enforced at the DB constraint layer |
| `test_policy_authority_capability_matching_fail_closed` | D — spoof/rotation/fail-closed capability |
| `test_policy_authority_uses_constant_time_compare` | D — `hmac.compare_digest`, no plain equality on the secret |
| `test_destination_routing_is_total_and_failclosed` | F — total, fail-closed destination classification |
| `test_audit_relay_never_claims_orchestrator_command_row` (Redis) | F — audit relay excludes command rows (real broker) |
| `test_dead_episode_version_changes_on_redeath_and_invalidates_stale_replay` | H/J — composite version determinism, attempts preserved |
| `test_destination_not_ready_blocks_execution_without_any_mutation` | K — readiness fail-closed, no consume/dead-row mutation |
| `test_replay_execution_rollback_restores_all_state` | I — replay execution rollback restores consume+dead-row+request |
| `test_one_active_replay_request_per_event_under_concurrency` | G/L — one active request per event under concurrency (hard) |
| `test_per_actor_replay_request_rate_limit_concurrency_characterisation` | L — per-actor cap concurrency (finding L-1) |
| `test_production_approval_reference_is_only_nonempty_checked` | M — reference only non-empty-checked (finding M-1) |
| `test_feature_gates_off_produce_zero_side_effects` | O — gates off produce zero DB side effect |

## Finding evidence

- **M-1** (`test_production_approval_reference_is_only_nonempty_checked`): a production-effect
  authorization consumed successfully with a bogus non-empty reference; an absent reference was
  correctly blocked with `production_approval_required`. The reference is not resolved to a real
  production approval.
- **L-1** (direct measurement): per-actor cap = 2, 8 concurrent requests across distinct events →
  8 created (overshoot); the subsequent sequential request was `rate_limited` (exact serial
  enforcement).

## Quality gates (reviewer's changed files)

`ruff check`, `black --check`, `mypy` all clean on
`tests/test_step66c4_be3_combined_review.py` and `scripts/verify_step66c4_be3_combined_review.py`;
`git diff --check` clean; secret/internal-identifier scan clean.

## Regression note

The four BE3 suites + the three BE1/BE2 remediation suites reproduced 0 skipped. Broader backend
regression was not re-run in full for this review; the implementation records report pre-existing
Redis-dependent BE2 skips unrelated to BE3 — those are pre-existing and non-mandatory for this
review, and the one Redis-exercising path mandated here (audit-relay routing) was run against a real
ephemeral Redis 7 and passed.

---
_Non-production only. No production action. No internal IP addresses, SSH aliases, private
hostnames, usernames, or credentials appear in this record — only neutral labels._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
