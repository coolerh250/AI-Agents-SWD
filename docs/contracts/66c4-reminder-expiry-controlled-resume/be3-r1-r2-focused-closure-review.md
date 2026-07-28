# Step 66C.4-BE3-R-FC — Focused Findings-Closure Review (M-1, L-1, R2-1)

> **Focused closure by the ORIGINAL Step 66C.4-BE3-R independent reviewer. NOT a new full review,
> NOT a new reviewer, NO additional subagents. Verifies ONLY the closure of findings M-1, L-1, and
> R2-1 and their directly-affected regression. Authorizes NO merge, NO deployment, NO shared-migration
> application, NO gate activation. `production_executed_true_count` remains 0. This record is
> APPEND-ONLY: it does not modify or weaken the original BE3-R verdict, findings, or evidence.**

## Continuity and scope

- Reviewer continuity: performed by the same independent reviewer who produced
  `be3-combined-independent-review.md` (`BE3_TECHNICAL_VERDICT: PASS`, original review commit
  `5626403` on branch `review/66c4-be3-combined-security-transaction`). The reviewer did not
  participate in the R1/R2 implementation and did not accept the implementation self-verifiers or
  records as sufficient evidence — every check below was independently re-derived and re-run against
  real PostgreSQL 16.
- Canonical main: `5745ab7`. Original reviewed feature head: `6323972`.
- R1 remediation: `b1bac36` (M-1 registry + L-1 advisory lock). R2 remediation / current feature
  head: `5a413bf` (R2-1 resume production-effect). Closure diff reviewed: `6323972..5a413bf`.
- Draft PR #20: remained Draft/OPEN/unmerged and untouched.
- The feature head `5a413bf` was merged into the review branch for in-tree inspection/verification;
  the focused-closure artifacts were then added as a separate closure commit. No implementation file
  was modified by the reviewer.

## Final technical verdict

```
STEP66C4_BE3_R1_R2_FOCUSED_CLOSURE_VERIFY: PASS   (closure process + artifacts complete)
BE3_TECHNICAL_VERDICT: PASS                        (all three findings independently CLOSED)
```

M-1, L-1, and R2-1 are each independently CLOSED. No new Critical/High finding; no new
future-activation-blocking Medium finding directly related to the three remediations. Mandatory
focused-closure suites: 0 failed / 0 skipped. No implementation modified by the reviewer; no shared
migration applied; no deployment; no activation.

---

## M-1 — production-approval reference now resolves against an authoritative registry — CLOSED

**Registry (migration 035 `production_action_approvals`).** Independently confirmed to be the
authoritative source, NOT a non-empty string / Stage-31 LLM proposal approval / Admin-Console
governed-action record / client assertion. It is:
- action-bound (`chk_paa_action_type`), resource-type + resource-id bound (same `resource_type` /
  `resource_id` as the resume/replay authorization it backs — resource-scoped, not task-scoped),
  team/project-bound (`UUID NOT NULL`), resource-state-version-bound (`resource_state_version`),
  time-bound (`chk_paa_expiry_after_grant`, 1s–24h), revocable-before-consume (`revoked_at`),
  single-use (`consumed_at` + `state='consumed'`, `chk_paa_not_consumed_and_revoked`), durably
  decided (`granted_by` / `granted_role` / `granted_at`), and transactionally consumable
  (`consumed_by_authorization_id` FK → `resume_replay_authorizations`).

**Actor boundary.** `production_approval_model.can_grant` = `role in TASK_ROLES and role in
{reviewer_approver, platform_admin}` (canonical pair; no second RBAC). Independently reproduced:
`agent_operator` and `pm_engineering_lead` → `rbac_denied`; a Service Identity → `rbac_denied`;
`reviewer_approver` / `platform_admin` → granted. There is NO HTTP grant/revoke endpoint (no API
file wires the grant/revoke service or repository), no startup/runtime caller; grant/revoke are
internal-only foundation ops in this stage.

**Resolution checks (resume AND replay, same shared `authorization_service.consume` resolver).**
Independently reproduced — a valid granted approval bound to the same action/resource/scope/version
is allowed; every one of missing / non-UUID / unknown / revoked / expired / already-consumed /
wrong-action / wrong-resource / wrong-team-project / stale-version is BLOCKED with the authorization
left unconsumed and the approval left unconsumed. Reason codes map 1:1 to the failure
(`production_approval_invalid_reference` / `_not_found` / `_already_consumed` / `_already_revoked` /
`_expired` / `_wrong_action` / `_wrong_resource` / `_wrong_scope` / `_stale_state`), all under one
result kind `production_approval_required`. A `None`/empty reference is fail-closed even earlier by
the policy layer (`production_approval_required`) before the resolver runs.

**Transaction / locks (no TOCTOU).** The resolver `SELECT … FOR UPDATE`-locks the approval row
before any check, so the informational checks and the final consuming CAS observe the SAME locked
row; the CAS re-binds every predicate (action/resource/team/project/version/unconsumed/unrevoked/
unexpired). Approval read+consume, BE3 authorization consume, and the audit/command/replay mutation
all run in ONE PostgreSQL transaction (the caller's). Independently reproduced:
- concurrent revoke-vs-consume on the same approval → exactly one succeeds, never both (row lock
  serialization);
- a post-approval-consume authorization CAS failure raises `RuntimeError` → the whole transaction,
  including the approval consume, rolls back (approval stays `granted`, authorization stays
  unconsumed) — no half-mutation;
- an injected audit-outbox insert failure during replay execute rolls back the approval consume, the
  authorization consume, AND the dead-row requeue together (dead row stays `dead`).

**Verdict: CLOSED.**

## L-1 — per-actor replay-request rate cap is now concurrency-safe — CLOSED

**Advisory-lock key.** `acquire_actor_rate_limit_lock` issues
`pg_advisory_xact_lock(hashtextextended($1, 0))` where `$1 =
"be3-replay-actor-rate:{team_id}:{project_id}:{actor_id}"`. Independently confirmed: it uses a
PostgreSQL server-side hash (`hashtextextended`), NOT Python's built-in `hash()`, so the key is
deterministic across processes and restarts; a hash collision between two different keys can only
cause extra harmless serialization (the COUNT is still exactly scoped by team+project+actor), never
a loosened/merged cap. It is a transaction-scoped advisory lock (auto-released at commit/rollback),
acquired BEFORE `lock_outbox_event` (consistent lock order, no self-deadlock), and never leaks a
session-level lock or pins/leaks the connection.

**Hard-cap behaviour (real PostgreSQL 16).** Independently reproduced:
- 20 concurrent requests, cap 10 → exactly 10 created / 10 `rate_limited`;
- 50 concurrent requests, cap 3 → exactly 3 created (never exceeds);
- same idempotency key, 6 concurrent → exactly one durable row (counted once);
- same actor across different team/project → independent caps (each allowed);
- a rolled-back request transaction releases the advisory lock (a fresh session can immediately
  re-acquire the same key);
- `platform_admin` is still capped (no bypass); invalid config (`0` / `abc`) fails closed (raises);
- a request older than the rolling 24h window no longer counts against the cap;
- the per-event "3 successful manual replays" hard cap is unchanged (still enforced).
Every successfully-created request counts toward the storm cap and is not retroactively decremented
by a later reject/cancel/expire (the COUNT is over all rows in the window regardless of later state).

**Verdict: CLOSED.**

## R2-1 — resume production-effect is now server-derived and state-version-bound — CLOSED

**Authoritative source.** `resume_request_model.authoritative_production_effect(task_row)` returns
`bool(task_row.get("production_effect", True))` — derived from `operator_tasks.production_effect`
(BOOLEAN NOT NULL), read under the SAME `lock_task` row lock already taken for eligibility, with a
fail-closed default of production-effect if ever unresolvable. No request-body / query / header
authority.

**Client field behaviour.** `ResumeRequestCreate` no longer declares `production_effect`; the
service function `request_resume` no longer accepts it as a parameter. Independently confirmed:
`production_effect` is absent from `ResumeRequestCreate.model_fields`, and a client that sends it
anyway is silently dropped by Pydantic (it never reaches the model attribute). This silent-ignore is
consistent with the existing API convention and does not affect classification — recorded as a
non-blocking observation, not a finding.

**Request derivation / state-version.** `resource_state_version(clar, task)` folds the server-derived
`production_effect` into the canonical version string (`status:answer_ref:production_effect`), and
`request_resume` derives it under the task lock and stores it on both the request and the
authorization. Independently reproduced: a production task → production-effect authorization
(consume then requires a valid registry approval); a non-production task → non-production
authorization (consume allowed without an approval); a client value cannot upgrade or downgrade
either.

**Authorize + consume revalidation and races.** `authorize_resume` and `prepare_execution` recompute
`resource_state_version(clar, task)` under lock and reject a mismatch as `stale_state`.
Independently reproduced: a task whose classification flips (non-production → production) after the
request is recorded causes `authorize_resume` to return `stale_state`, with the request left
`authorization_pending`, no authorization consumed, and no side effect.

**Scope.** The authoritative task lookup binds `task_id` + the caller's team/project and the
clarification↔task relationship. Independently reproduced: cross-project caller scope →
`not_found_masked`; NULL scope → fail closed.

**Verdict: CLOSED.**

## Activation gate

`be3-runtime-activation-gate.md` §A.0/§A.1 now record M-1 (IMPLEMENTED / TESTED / TRANSACTIONALLY
VERIFIED / FAIL-CLOSED), L-1 (CONCURRENCY-SAFE / POSTGRESQL-VERIFIED), and R2-1 (SERVER-DERIVED /
STATE-VERSION-BOUND / TRANSACTIONALLY REVALIDATED / CLIENT-DOWNGRADE-PROOF / POSTGRESQL-VERIFIED).
Independently confirmed that the original 11 activation prerequisites (Section A) are preserved and
NOT marked complete ("items 1-11 below remain required in full"), and Section C still authorizes NO
deployment, NO application of any BE3 migration to a shared database, and NO activation, with
`production_executed_true_count` remaining 0. **Deployment readiness — NO; Runtime activation
readiness — NO; Shared migration readiness — NO.**

## Findings

- Critical: none. High: none.
- New activation-blocking Medium (related to the three remediations): none.
- Low / observation (non-blocking): R2-obs-1 — the API silently drops an unrecognized client-sent
  `production_effect` field (Pydantic default). This matches the existing API convention and cannot
  influence the server-side classification (proven), so it is a hardening note, not a security
  finding. Optionally the model could `model_config = ConfigDict(extra="forbid")` to reject unknown
  fields loudly; not required for closure.
- Original BE3-R findings M-1 and L-1 are hereby CLOSED; R2-1 (surfaced during BE3-R1) is CLOSED.

## Behavioural-inversion confirmation (positive evidence M-1 is fixed)

The original BE3-R combined-review suite included a finding-DEMONSTRATION test
(`test_production_approval_reference_is_only_nonempty_checked`) that asserted the PRE-fix behaviour
(a bogus non-empty reference consumes successfully). Run unchanged against the fixed head `5a413bf`,
that single test now FAILS because the bogus reference is rejected as
`production_approval_invalid_reference` — a positive confirmation that M-1 is closed. Per the
append-only rule, that historical test is NOT modified or weakened; its inversion is documented here
and in the evidence record.

## Recommendation

- Required remediation: none for closure. Optional non-blocking hardening: `extra="forbid"` on
  `ResumeRequestCreate` (R2-obs-1).
- PR #20 merge readiness: the three findings are closed at the code level; BE3-M (non-squash merge of
  PR #20) remains gated on separate explicit Product Owner authorization.
- Deployment / runtime-activation readiness: NO — the full 11-item activation gate plus separate
  explicit PO authorization remain required and unchanged.
- Next authorized step: Product-Owner-authorized BE3-M merge decision. No activation.

---
_Non-production only. No production action. No production data. No internal IP addresses, SSH
aliases, private hostnames, usernames, or credentials appear in this record — only neutral labels
("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
