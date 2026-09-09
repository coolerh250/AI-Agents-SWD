# AT-D34 — AT-M3.6B.2 Test Runtime Database Migration Alignment Authorization

> **Product Owner decision record. Authorizes ONE bounded action: applying exactly the existing
> canonical migrations 039 through 045, in canonical order, to the internal non-production test
> runtime's PostgreSQL database, using the repository's existing forward-only migration mechanism.
> It authorizes NO new migration, NO migration-file edit, NO application-code change, NO Anthropic
> call, NO live-gate enablement, and NO reactivation of the AT-D33 budget policy.
> `production_executed_true_count: 0`.**

```text
AT-D34:                      RESOLVED / BINDING
Recorded_on:                 2026-09-09
Recorded_by:                 Product Owner
Canonical_main_at_decision:  c35a12e518106f7326f915449100814c6856d22e
Branch:                      (docs-only, direct to main)
Depends_on:                  AT-D32 (docs/decisions/at-d32-at-m3-6b-2-live-validation-authorization.md)
                             AT-D33 (docs/decisions/at-d33-at-m3-6b-2-live-validation-budget-policy-provisioning-authorization.md)

TEST RUNTIME MIGRATION ALIGNMENT:        AUTHORIZED
THIS SLICE:                              AUTHORIZED
ANTHROPIC CALLS AUTHORIZED BY THIS RECORD: 0
REASONING_LIVE_NETWORK_ENABLED:          false throughout -- not touched by this record
AT-D33 BUDGET POLICY:                    INACTIVE -- must remain inactive throughout and after
AT-M4:                                   NOT AUTHORIZED
Production:                              NOT GRANTED
production_executed_true_count:          0
```

## 1. What this record is for

A prior AT-M3.6B.2 Live Validation execution attempt's task prompt asserted, without corroboration in
`source/progress.md` or canonical main, that a "Retry 1" session had already run and hit a
`reasoning_invocations` schema error. That specific claim did not check out — canonical main had not
moved and no such session was recorded — and was reported as a prompt/docs conflict rather than acted
on at face value. Independent, direct inspection of the test runtime's own database, however,
confirmed a genuine underlying problem: `reasoning_invocations` carries only migration 037's original
DDL (no `artifact_type` column, `provider_mode` not admitting `'live'`, `reasoning_verb` not admitting
`'decompose_plan'`), and several migrations required for AT-M3.6B.1/AT-M3.6B.2 reasoning contracts
have never been applied to this runtime. This record authorizes closing that gap, on the strength of
that independent verification, not the unverified prompt claim.

## 2. Migration state, as independently verified

```text
Applied to this runtime:      001-030, then 036-038 (AT-M2 team core, AT-M3.1 reasoning_invocations
                                base, AT-M3.2 goals/plan_revisions). Verified by direct table/column
                                inspection, not inferred from a ledger (none exists for this chain).
Pending, verified dependency-clean:  039-045 (AT-M3.3 bounded team discussion tables, AT-M3.4's
                                reasoning_invocations durable-artifact alterations and
                                planning_decisions, AT-M3.5 plan-execution-graph tables, AT-M3.6A's
                                audit timeline index, AT-M3.6B.1's provider_mode='live' /
                                failure_category widening, and the budget-events reservation columns).
                                Confirmed zero reference from any of 039-045 to any object outside
                                this set or to the 031-035 chain below.
Explicitly OUT OF SCOPE:      031-035 (a separate "BE3" clarification/resume/replay/production-
                                action-approval chain). Also absent from this database, but wired to
                                its own dedicated tool (`scripts/run_platform_migrations.py`) and its
                                own dedicated `PLATFORM_MIGRATIONS_DATABASE_URL` -- that tool's own
                                docstring states it is "not wired into any deployment, CI job, or
                                shared runtime" and applying it is "a separate, explicit operator
                                action." This gap pre-dates this task, is unrelated to the reasoning
                                path, and this record does not authorize touching it.
```

## 3. Authorized scope

```text
Action:                        apply exactly migrations 039_at_m3_3_bounded_team_discussion.sql
                                through 045_at_m3_6b_1_budget_reservation.sql, in that numeric order,
                                using the repository's existing forward-only `psql -f
                                migrations/NNN_*.sql` mechanism (no ledger write required by that
                                mechanism; each file is independently idempotent -- `CREATE ... IF NOT
                                EXISTS`, `DROP CONSTRAINT IF EXISTS` before `ADD CONSTRAINT` -- and
                                each is wrapped in its own transaction)
Environment:                    internal non-production test runtime only
Not authorized:                 migrations 031-035; any new migration; any edit to any migration
                                file; any application code change; any Anthropic call, real or
                                diagnostic; REASONING_LIVE_NETWORK_ENABLED=true anywhere; reactivating
                                or recreating the AT-D33 budget policy (policy_id
                                `d29ad073-9f7c-48b4-876d-cd3cb1343b40`); AT-M4; HumanApproval
                                mutation; production action
Required before write:          a recoverable PostgreSQL backup of the test-runtime database, with a
                                non-destructive usability check, before the first migration is applied
Required after each migration:  verification that it completed; a failure STOPS the chain rather than
                                continuing or being skipped
Required evidence:              exact pre- and post-migration schema state for the objects each
                                migration touches; a zero-network proof that
                                `ReasoningStore.get_by_correlation_id()` and a `ReasoningService`
                                preflight-boundary dry run no longer fail on stale schema; a bounded
                                regression run restricted to mock/fake providers only
```

Note on the AT-D33 budget policy: it was created **active** by AT-D33 (policy_id
`d29ad073-9f7c-48b4-876d-cd3cb1343b40`). Direct inspection immediately before this record was drafted
found it now `inactive` (`updated_at` roughly 23 minutes after `created_at`), with zero
`llm_budget_events` ever recorded against it and zero `reasoning_invocations` rows for provider
`anthropic` — confirming no real call or spend occurred; something changed only the row's `status`
directly, outside any budget-consuming flow, for a reason this record cannot establish. This record
does not require or authorize changing its status either way; it only prohibits this migration-
alignment stage from creating a second policy, recreating this one, reactivating it, or otherwise
touching budget policy data. Its actual status must be verified, not assumed, during this stage's
runtime safety checks, and reported accurately regardless of what it turns out to be at that time.

## 4. What is NOT authorized

```text
Migrations 031-035, or any migration this record does not name           NOT AUTHORIZED
A new migration file, or an edit to any existing migration file          NOT AUTHORIZED
Any ReasoningService / ReasoningStore / AnthropicReasoningProvider / BudgetPolicyStore code change  NOT AUTHORIZED
Any Anthropic call, real or diagnostic                                    NOT AUTHORIZED
REASONING_LIVE_NETWORK_ENABLED=true (any process)                         NOT AUTHORIZED
AT-M4, HumanApproval mutation, production action                         NOT AUTHORIZED / NOT GRANTED
```

## 5. What this decision does NOT do

```text
Does NOT authorize any Anthropic call -- a separate Live Validation execution session, still bounded
   by AT-D32, performs that
Does NOT amend AT-D32 or AT-D33
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4 or any real work execution
Does NOT authorize applying migrations 031-035 or any migration this record does not name
Does NOT modify migration files, application code, or BudgetPolicyStore/ReasoningService semantics
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
