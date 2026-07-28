# Step 66C.4-BE3-RA-P — Runtime Activation Readiness Planning

> **Planning/inventory document only. This stage authorizes NO deployment, NO migration
> application, NO feature-gate enablement, NO runtime validation, and NO implementation PR. It
> classifies the current, code-verified state of every activation prerequisite and hands off a
> proposed (not authorized) execution sequence. Every stage in that sequence still requires its own
> separate, explicit Product Owner authorization before it starts.**

## 1. Baseline (confirmed before this planning began)

```text
Canonical main:        bf7bf55
BE3 merge commit:       284d706
Approved feature head:  5a413bf
Original review:        5626403
Focused closure:        2712ad4
local main == origin/main == bf7bf55:  YES
Working tree clean, no untracked files: YES
```

## 2. BE3 status (re-confirmed, unchanged by this stage)

```text
Step 66C.4-BE3: MERGED / NOT DEPLOYED / NOT RUNTIME VALIDATED / NOT ACTIVATED / NO SHARED
                MIGRATION / NO RUNTIME RESUME OR REPLAY
Sub-stages: BE3-A MERGED, BE3-B MERGED, BE3-C MERGED, BE3-R PASS, BE3-R1/R2 findings CLOSED,
            BE3-M PASS.
production_executed_true_count: 0 (unchanged by this planning stage; no execution path was ever
            touched by RA-P).
```

## 3. Ground rule applied throughout

**Code existing and being tested in an isolated ephemeral container is NOT the same as runtime
readiness.** Every classification below distinguishes "the logic is implemented and proven
correct" from "a real process, in a real shared environment, actually exercises it end-to-end."
Where BE3's own test suites (BE3-A/B/C/R1/R2/R-FC, 193+ PostgreSQL tests) already prove code
correctness, that is cited as evidence for the *implementation* half of a classification, never as
evidence of *runtime* readiness by itself.

## 4. Single most consequential finding (read this before the 11-item inventory)

**No process anywhere in this repository ever consumes a `DESTINATION_ORCHESTRATOR_COMMAND` outbox
row, and no process anywhere ever authenticates as the Service Identity or the Policy Authority
outside test helpers.** Concretely, verified by direct inspection:

```text
shared/sdk/tasks/replay_request_model.py::default_destination_readiness() -- its own docstring:
  "orchestrator_command: no consumer has been built at all."
shared/sdk/tasks/outbox_relay.py -- the BE2 relay claims/publishes ONLY DESTINATION_AUDIT rows;
  DESTINATION_ORCHESTRATOR_COMMAND rows are explicitly out of its scope.
apps/orchestrator/src/operations_resume_api.py:12 -- "resume_service.prepare_execution ... it is
  NOT exposed here."
apps/orchestrator/src/operations_replay_api.py:13 -- "replay_service.execute_authorized_replay ...
  it is NOT exposed here and there is NO public [execute endpoint]."
grep for `is_service_identity=True` across the whole repo: 12 matches, ALL under `tests/` (test
  helpers in the BE3-A/B/B-C1/C/R1/R2 suites). Zero matches in any `apps/` or `shared/sdk/` file.
```

This means: even with all four feature gates flipped true today, `prepare_execution` and
`execute_authorized_replay` would still never run, because nothing in any shared runtime is
authorized or wired to call them. Activation readiness therefore requires **new implementation
work** (a Service-Identity-authenticated caller, and for resume specifically a downstream consumer
of the resulting outbox command), not merely turning on switches. This drives the sequence in
`be3-runtime-activation-stage-sequence.md`.

## 5. Activation-gate inventory (the 11 items in `be3-runtime-activation-gate.md` §A)

Each item is classified into exactly one of: `IMPLEMENTED_AND_VERIFIED`,
`IMPLEMENTED_NOT_RUNTIME_VALIDATED`, `PARTIALLY_IMPLEMENTED`, `NOT_IMPLEMENTED`,
`BLOCKED_BY_DEPENDENCY`, `REQUIRES_PRODUCT_DECISION`, `REQUIRES_EXTERNAL_RESOURCE`.

### Gate 1 — Migration 031 (BE2 outbox schema) applied to the target runtime

```text
Classification:       NOT_IMPLEMENTED
Security purpose:      base schema (clarification_lifecycle_outbox + 6 lifecycle columns) that
                        031-035 all build on.
Implementation:        migrations/031_clarification_lifecycle_outbox_foundation.sql (+_down)
Evidence:               be1-migration-and-compatibility-record.md -- additive, idempotent, rollback
                        proven in ISOLATED ephemeral PG16 only.
Shared-runtime state:   never applied to any shared database (BE1-M / BE2-M status, unchanged).
Missing capability:     an executed, verified apply+rollback rehearsal on a shared-like runtime.
Upstream dependency:    none (lowest-numbered migration in this chain).
Downstream dependency:  gates 2, 5, 6, 7, 9, 10 all assume 031 is applied first.
Migration required:     this IS the migration.
Worker/relay/consumer:  none required to apply the migration itself.
Secret/external system: none.
PO decision required:   which runtime (dedicated isolated test runtime vs. the shared aiagents-test
                         stack) hosts the first rehearsal (see §8).
Rollback on failure:    apply *_down.sql; already proven in isolated PG16, never in a shared runtime.
Metrics before activation: none (schema-only; no traffic yet).
Risk level:             HIGH (schema change; per policy requires independent review even though
                        purely additive).
```

### Gate 2 — BE3 authorization migration (032/033/034/035) applied to the target runtime

```text
Classification:       NOT_IMPLEMENTED
Security purpose:      durable authorization, resume/replay request, and production-approval tables
                        that every BE3 security guarantee is built on.
Implementation:        migrations/032_be3_resume_replay_authorization.sql,
                        033_be3_resume_requests.sql, 034_be3_replay_requests.sql,
                        035_be3_production_action_approvals.sql (all four have matching *_down.sql).
Evidence:               193+ PostgreSQL tests across BE3-A/B/C/R1/R2/R-FC applied/rolled back these
                        migrations repeatedly in ISOLATED ephemeral containers; Stage-51's
                        migration-rollback catalog (shared/sdk/backup_dr/migration_catalog.py)
                        classifies all four as "reversible" (down script present).
Shared-runtime state:   never applied to any shared database.
Missing capability:     a rehearsal of 031+032+033+034+035 applied TOGETHER, in sequence, on a
                        shared-like runtime, with a combined rollback proof (035 has an FK to
                        032's authorization table; rollback order matters).
Upstream dependency:    Gate 1 (031 must precede).
Downstream dependency:  gates 3-10 (BE3 code cannot run against an unmigrated schema).
Migration required:     this IS the migration.
Worker/relay/consumer:  none required to apply the migration itself.
Secret/external system: none.
PO decision required:   same runtime decision as Gate 1; whether to migrate ahead of any gate
                        enablement (recommended) or bundle with first activation.
Rollback on failure:    apply *_down.sql files in reverse numeric order (035, 034, 033, 032);
                        proven only in isolated ephemeral containers.
Metrics before activation: table/index existence checks, row counts pre/post (should be 0 rows).
Risk level:             HIGH (schema change; independent review required by policy).
```

### Gate 3 — Lifecycle poller deployed and health/metrics verified in the target runtime

```text
Classification:       BLOCKED_BY_DEPENDENCY (on BE2's own still-open activation, not owned by BE3)
Security purpose:      detects reminder-due / expiry-due clarifications; the trigger that makes
                        resume eligibility (resume_eligible_at) meaningful in a live system.
Implementation:        apps/clarification-lifecycle-worker/src/main.py (BE2).
Evidence:               BE2 regression suite; never deployed (be2-merge-and-source-of-truth-record.md:
                        "NOT DEPLOYED / NOT RUNTIME VALIDATED / NOT ACTIVATED").
Shared-runtime state:   no service entry in infra/docker-compose/docker-compose.yml; not imported
                        by apps/orchestrator.
Missing capability:     a compose/k8s service definition, health endpoint exercised live, metrics
                        scraped by the existing Prometheus stack.
Upstream dependency:    Gates 1-2 (needs the migrated schema).
Downstream dependency:  Gate 9 (audit evidence flow), indirectly Gate 10 (E2E).
Migration required:     no (schema already covered by Gate 1).
Worker/relay/consumer:  YES -- this IS the worker; BE3 does not own it and cannot close this gate
                        alone. This is a genuine cross-stage dependency on a decision BE2-M
                        deliberately deferred.
Secret/external system: DB connection only (already provisioned for the shared stack).
PO decision required:   whether to activate the shared BE2 poller/relay NOW as a BE3 prerequisite,
                        or build a BE3-scoped, narrower audit-delivery path instead (see §8).
Rollback on failure:    stop the service; no schema mutation caused by the poller itself.
Metrics before activation: reminder/expiry counters (BE2 lifecycle_metrics.py already defines them).
Risk level:             MEDIUM (isolated runtime adapter, no authorization consume) once its own PO
                        decision is made; the decision itself is the blocker.
```

### Gate 4 — Outbox relay deployed and health/metrics verified in the target runtime

```text
Classification:       BLOCKED_BY_DEPENDENCY (same as Gate 3 -- BE2's own relay)
Security purpose:      publishes DESTINATION_AUDIT outbox rows (the durable evidence trail BE3
                        depends on for every resume/replay transition).
Implementation:        apps/clarification-outbox-relay/src/main.py + shared/sdk/tasks/
                        outbox_relay.py (BE2, extended for destination routing at BE3-B-C1).
Evidence:               BE2-R1 proved bounded retry/backoff/dead-letter end-to-end in isolated
                        ephemeral PostgreSQL 16 + Redis 7; never in a shared runtime.
Shared-runtime state:   no service entry in docker-compose; not activated anywhere.
Missing capability:     compose/k8s service definition, live health/metrics.
Upstream dependency:    Gates 1-2.
Downstream dependency:  Gate 9 (audit evidence must actually be delivered somewhere, not just
                        written to the outbox table), Gate 10 (E2E).
Migration required:     no.
Worker/relay/consumer:  YES -- this IS the relay; same cross-stage dependency as Gate 3.
Secret/external system: Redis connection (already provisioned for the shared stack).
PO decision required:   same as Gate 3 (§8) -- these two gates should be decided together since
                        BE3's own audit trail rides on this exact relay.
Rollback on failure:    stop the service; relay only reads/publishes, never mutates outbox state
                        destructively (claims -> publishes -> marks published, or leaves dead).
Metrics before activation: publish success/failure counters, dead-row count (already defined).
Risk level:             MEDIUM (once the PO decision in Gate 3/4 is made).
```

### Gate 5 — Retry/DLQ path verified end-to-end (bounded retries -> dead -> operator visibility)

```text
Classification:       PARTIALLY_IMPLEMENTED
Security purpose:      guarantees no resume/replay audit evidence or command is silently lost;
                        bounded retries with a visible terminal (dead) state.
Implementation:        shared/sdk/tasks/lifecycle_outbox.py (MAX_RETRIES=4, MAX_PUBLISH_ATTEMPTS=5,
                        backoffs 30/120/600/3600s -- BE2-R1).
Evidence:               proven end-to-end for the AUDIT destination in isolated ephemeral
                        PostgreSQL+Redis (BE2-R1). NEVER exercised for the ORCHESTRATOR_COMMAND
                        destination, because no consumer exists for that destination at all (see
                        §4) -- a resume.execution_requested row would sit "pending" forever today
                        with no retry/backoff/dead transition ever evaluated against it.
Shared-runtime state:   not exercised in any shared runtime for either destination.
Missing capability:     end-to-end proof in a shared-like runtime; the orchestrator-command
                        consumer (§4) before the DLQ semantics for THAT destination can even be
                        exercised once.
Upstream dependency:    Gates 1-2, 4 (audit path), and the new orchestrator-command consumer work
                        (RA-4 in the stage sequence) for the command path.
Downstream dependency:  Gate 10 (E2E).
Migration required:     no.
Worker/relay/consumer:  the audit-destination retry path reuses the BE2 relay (Gate 4); the
                        command-destination retry path needs the NEW consumer from §4.
Secret/external system: none beyond Gate 3/4's.
PO decision required:   none beyond Gates 3/4/§4.
Rollback on failure:    dead rows are inert (no side effect); operator-visible via direct DB query
                        today (no Admin Console surface -- see the standalone-areas section below).
Metrics before activation: dead-row count, retry-attempt histogram (already defined for audit; not
                        yet defined for command destination).
Risk level:             HIGH (consumer concurrency once built).
```

### Gate 6 — Rollback tested (disable dispatch + revert schema, no data loss)

```text
Classification:       PARTIALLY_IMPLEMENTED
Security purpose:      a clean, reversible path out of activation if something goes wrong.
Implementation:        all four feature gates (BE3_RESUME_API_ENABLED, BE3_RESUME_COMMAND_ENABLED,
                        BE3_REPLAY_API_ENABLED, BE3_REPLAY_EXECUTION_ENABLED) are read fresh via
                        os.environ.get on every call (no caching), so flipping them back to "false"
                        takes effect immediately with no restart-ordering hazard. Migrations 031-035
                        all carry *_down.sql, classified "reversible" by the Stage-51 catalog.
Evidence:               gate-read behavior verified by code inspection (no module-level caching of
                        the env value anywhere in resume_request_model.py / replay_request_model.py);
                        migration down-scripts exercised repeatedly in isolated ephemeral containers.
Shared-runtime state:   the COMBINED rehearsal ("deploy, activate, then roll everything all the way
                        back on a live shared-like runtime with zero data loss") has never been
                        performed.
Missing capability:     one dedicated rehearsal exercising the full up -> partial-activation ->
                        down sequence on a disposable runtime that mirrors the shared stack.
Upstream dependency:    Gates 1-2.
Downstream dependency:  none (this gate protects every later gate).
Migration required:     applies the down scripts; no new migration.
Worker/relay/consumer:  whichever were started during the rehearsal must be cleanly stoppable.
Secret/external system: none beyond what's already provisioned.
PO decision required:   which disposable runtime hosts this rehearsal (see §8, same decision as
                        Gates 1/2).
Rollback on failure:    this gate IS the rollback rehearsal; a failure here blocks every later gate.
Metrics before activation: none (this is itself the pre-activation gate).
Risk level:             HIGH (migration rollback under realistic conditions).
```

### Gate 7 — Producer cutover plan approved

```text
Classification:       REQUIRES_PRODUCT_DECISION
Security purpose:      BE2's framing of this gate ("does an existing producer begin writing the
                        outbox") does not map directly onto BE3, which has no external producer --
                        the closest BE3 analog is "who is the first real Policy Authority and
                        Service Identity in a live environment" (see Gate 11/§8).
Implementation:        n/a (decision, not code).
Evidence:               n/a.
Shared-runtime state:   n/a.
Missing capability:     an explicit Product Owner decision reinterpreting this gate for BE3 (see
                        §8 -- "Who grants production_action_approvals at runtime?" and "What is the
                        canonical operator identity source?" are the concrete sub-decisions).
Upstream dependency:    none.
Downstream dependency:  Gates 8-11.
Migration required:     no.
Worker/relay/consumer:  no.
Secret/external system: depends on the decision (a real automated policy engine may need its own
                        credential -- see Gate 11).
PO decision required:   YES -- this entire gate IS a decision (§8).
Rollback on failure:    n/a.
Metrics before activation: n/a.
Risk level:             CRITICAL (this decision gates whether any production-effect path can ever
                        be exercised for real).
```

### Gate 8 — Resume/replay RBAC verified (permission matrix + two-person replay control enforced)

```text
Classification:       IMPLEMENTED_NOT_RUNTIME_VALIDATED
Security purpose:      only the correct canonical TASK_ROLES may request/authorize/consume; replay
                        requires a distinct approver from the requester.
Implementation:        shared/sdk/tasks/authorization_policy.py, resume_service.py, replay_service.py.
Evidence:               extensively proven across BE3-A/B/C/R1/R2/R-FC (193+ real-PostgreSQL tests,
                        plus the R-FC independent reviewer's own 22-test reproduction) -- but every
                        one of those runs was against an isolated, single-purpose, single-tenant
                        ephemeral container, never a live multi-operator shared runtime.
Shared-runtime state:   never exercised live.
Missing capability:     a runtime E2E proving the SAME RBAC/two-person guarantees hold when real
                        concurrent operators share the runtime (this is Gate 10's job).
Upstream dependency:    Gates 1-2.
Downstream dependency:  Gate 10.
Migration required:     no.
Worker/relay/consumer:  no.
Secret/external system: canonical operator identity source is still undecided (§8).
PO decision required:   "What is the canonical operator identity source?" (§8).
Rollback on failure:    n/a (read-only verification).
Metrics before activation: RBAC-denial counters (not yet instrumented -- see the metrics area below).
Risk level:             HIGH (authorization consume) per the code-level guarantees; the runtime
                        dimension is MEDIUM once Gate 10 is scheduled.
```

### Gate 9 — Audit evidence verified (every transition produces durable, content-safe evidence)

```text
Classification:       IMPLEMENTED_NOT_RUNTIME_VALIDATED
Security purpose:      every resume/replay/production-approval transition must be reconstructable
                        after the fact without exposing secrets.
Implementation:        build_safe_audit_payload-style helpers across authorization_model.py,
                        resume_request_model.py, replay_request_model.py,
                        production_approval_model.py (forbidden-value-marker scanning, e.g.
                        "password", "secret", "token", "dsn=", "postgres://", "redis://").
Evidence:               proven at the code/test level throughout BE3; never verified that the
                        resulting DESTINATION_AUDIT outbox rows are actually DELIVERED anywhere an
                        operator can see them, because the relay that would deliver them (Gate 4)
                        is not activated, and there is no Admin Console surface for BE3 at all (see
                        the standalone-areas section).
Shared-runtime state:   audit rows are written durably to the DB (proven); never relayed/surfaced.
Missing capability:     Gate 4's activation, plus an Admin Console/visibility surface (currently
                        NOT_IMPLEMENTED, out of BE3's originally authorized scope -- BE3 was
                        explicitly "no frontend").
Upstream dependency:    Gates 1-2, 4.
Downstream dependency:  Gate 10.
Migration required:     no.
Worker/relay/consumer:  Gate 4's relay.
Secret/external system: none beyond Gate 4's.
PO decision required:   "What evidence must appear in Admin Console?" (§8).
Rollback on failure:    n/a.
Metrics before activation: audit-row write success rate (implicit in outbox row counts).
Risk level:             MEDIUM for the write path (already proven); the visibility gap is a product
                        decision, not a security risk by itself.
```

### Gate 10 — Runtime E2E passed (resume and replay, full path) on an isolated runtime

```text
Classification:       NOT_IMPLEMENTED
Security purpose:      the single end-to-end proof that the whole chain -- request, authorize,
                        gated dispatch, orchestrator confirmation (resume) / internal replay adapter
                        (replay), dead->pending -- works together in a real running system, not just
                        in unit/integration tests against a throwaway container.
Implementation:        n/a (this is the validation activity itself, not a code artifact).
Evidence:               none yet; structurally cannot be attempted with today's code, because the
                        "orchestrator confirmation" step for resume has no consumer to produce it
                        (see §4), and no real Policy Authority/Service Identity exists to drive the
                        authorize/consume steps outside test helpers.
Shared-runtime state:   n/a.
Missing capability:     everything in §4, plus Gates 1-2 (migrated schema) and Gates 3/4 (if the
                        audit path is required for this E2E's evidence checks).
Upstream dependency:    Gates 1, 2, 3, 4, 7, 8, 9, and the new consumer/caller work in §4.
Downstream dependency:  Gate 11 (the go/no-go review consumes this gate's result).
Migration required:     no (assumes Gates 1-2 already applied).
Worker/relay/consumer:  the new orchestrator-command consumer (resume) and a Service-Identity-
                        authenticated internal caller (replay) from §4.
Secret/external system: whatever Gate 11/§8 decides for Policy Authority/Service Identity.
PO decision required:   "Which environment will host first runtime validation?", "What events are
                        allowed during initial validation?", "What is the maximum number of official
                        resume/replay operations?", "What rollback threshold aborts validation?" (§8).
Rollback on failure:    the isolated runtime is disposable; no shared-runtime impact if scoped
                        correctly (a §8 decision, not yet made).
Metrics before activation: this gate DEFINES the metrics to watch (§8's "allowed events" answer).
Risk level:             CRITICAL (first real exercise of the production-effect path end-to-end).
```

### Gate 11 — Product Owner deployment authorization (explicit, per-runtime)

```text
Classification:       REQUIRES_PRODUCT_DECISION
Security purpose:      no BE3 capability may ever go live without a human, explicit, per-runtime
                        decision -- the final backstop behind every other gate.
Implementation:        n/a (organizational control, not code).
Evidence:               this planning stage itself, and every prior BE3 stage, deliberately stopped
                        short of this authorization each time it came up.
Shared-runtime state:   n/a.
Missing capability:     the authorization itself; not something this planning stage can supply.
Upstream dependency:    all other gates.
Downstream dependency:  none (terminal gate).
Migration required:     no.
Worker/relay/consumer:  no.
Secret/external system: no.
PO decision required:   YES, always, per runtime, non-delegable.
Rollback on failure:    n/a.
Metrics before activation: n/a.
Risk level:             CRITICAL by definition.
```

## 6. Standalone areas from §5 not already fully covered by a single numbered gate above

```text
Command acknowledgement and idempotency:
  PARTIALLY_IMPLEMENTED / BLOCKED_BY_DEPENDENCY. The DATA MODEL supports it today -- outbox rows
  have a UNIQUE idempotency_key, and BE3-B's own design uses command_id = the outbox row id so a
  re-delivered command is trivially recognizable. But since no consumer exists (§4), there is no
  real acknowledgement flow to verify yet.

Production approval grant lifecycle (runtime-facing half):
  NOT_IMPLEMENTED. The registry (migration 035) and its resolver are IMPLEMENTED_AND_VERIFIED at
  the data layer (BE3-R1, re-verified independently at BE3-R-FC). But
  production_approval_service.grant_production_approval / revoke_production_approval have NO HTTP
  endpoint and no caller in any shared runtime -- a real reviewer_approver or platform_admin has no
  way to actually grant an approval today. This is exactly gate 7/§8's open decision.

Policy Authority credential provisioning:
  PARTIALLY_IMPLEMENTED / REQUIRES_EXTERNAL_RESOURCE / REQUIRES_PRODUCT_DECISION. The
  authentication MECHANISM is fully built (apps/orchestrator/src/operations_resume_api.py: a fixed
  server-configured principal id via BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID, plus a rotating
  capability header compared with hmac.compare_digest). But no environment sets these variables
  (confirmed: no match in infra/secrets, infra/vault, infra/docker-compose, or any Kubernetes
  values file), so the mechanism is unconditionally fail-closed everywhere today, and there is no
  real automated policy/safety engine process that would ever present these credentials.

Service Identity authentication:
  NOT_IMPLEMENTED (runtime-facing). `is_service_identity=True` is constructed only in test-helper
  code (12 call sites across the BE3-A/B/B-C1/C/R1/R2 test suites, all under `tests/`); a repo-wide
  search confirms ZERO call sites in any `apps/` or `shared/sdk/` production module. No production
  authenticator resolves a real caller into this flag.

Metrics / logs / traces / health (BE3-specific):
  NOT_IMPLEMENTED. shared/sdk/tasks/lifecycle_metrics.py has no resume/replay/production-approval
  counters (only BE2's own internal replay_dead metric). The general Prometheus/Grafana/Tempo/
  Alertmanager stack is already running in infra/docker-compose/docker-compose.yml and would need
  new BE3-specific series added, not a new stack.

Activation rollback:
  see Gate 6.

Runtime reconciliation:
  NOT_IMPLEMENTED. No job exists to detect/report orphaned pending resume/replay requests or
  expired-but-unconsumed authorizations. Partially self-mitigating: every authorization/approval
  carries its own expires_at, so a stale row is self-describing even without an active reconciler,
  but nothing currently surfaces or cleans these up.

Security and scope isolation:
  IMPLEMENTED_AND_VERIFIED at the code level (exact NULL-safe team/project scoping, cross-tenant
  masking, re-verified independently at BE3-R and BE3-R-FC); IMPLEMENTED_NOT_RUNTIME_VALIDATED for
  the "real multi-tenant shared runtime" dimension specifically (only ever exercised in
  single-purpose isolated containers).

Operator/Admin Console visibility:
  NOT_IMPLEMENTED. Confirmed zero Admin Console/frontend changes in any BE3 commit (BE3 was
  explicitly scoped as "no frontend" throughout BE3-A/B/C).

Runbook and incident response:
  NOT_IMPLEMENTED. `be3-runtime-activation-gate.md` is a contract/gate document, not an operational
  runbook; no BE3-specific incident-response procedure exists yet.
```

## 7. Product decisions inventory (open; this document does not answer any of these)

```text
1. Who grants production_action_approvals at runtime? (a named role process, an Admin Console
   action, or something else -- the registry and RBAC boundary exist; the operational answer does
   not.)
2. Where will approval requests be shown to a human approver? (no Admin Console surface exists.)
3. What is the canonical operator identity source for a live runtime? (test suites use synthetic
   principal ids; production needs a real identity provider binding.)
4. What is the Service Identity authentication mechanism? (the policy-model flag exists; nothing
   authenticates a real caller into it.)
5. What is the Policy Authority secret delivery mechanism? (the env-var + capability-header
   mechanism exists in code; no Vault/secret-manager entry, no real policy engine process.)
6. Which environment will host first runtime validation? (a dedicated disposable runtime, or the
   existing shared aiagents-test stack -- different blast-radius and rollback implications.)
7. What events are allowed during initial validation? (synthetic-only, or real-but-low-stakes
   clarifications -- affects both realism and risk.)
8. What is the maximum number of official resume/replay operations during initial validation?
   (a hard cap, analogous to the existing BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT pattern, but for the
   validation window itself.)
9. What rollback threshold aborts validation? (e.g., N consecutive failures, any data-loss signal,
   any unexpected production-effect classification -- undefined today.)
10. What evidence must appear in Admin Console before activation is considered complete? (ties to
    standalone area "Operator/Admin Console visibility" above.)
11. What is the initial activation boundary -- API only, command path, or replay path? (the
    proposed stage sequence assumes API-only first, but this is a recommendation, not a decision.)
```

## 8. Cross-cutting note on Gates 3/4 (BE2 dependency)

Gates 3 and 4 are BE2's own poller and relay, not BE3-owned code. BE2-M's merge record already
records them as "NOT DEPLOYED / NOT RUNTIME VALIDATED / NOT ACTIVATED" and that status is
unchanged. BE3's own audit-evidence delivery (Gate 9) rides on the SAME relay. This planning stage
flags, but does not resolve, the product decision of whether activating BE2's poller/relay now (as
a BE3 prerequisite) is in scope, or whether a narrower BE3-specific audit-delivery path should be
built instead -- see product decision items 1-2 in principle, though it is not literally one of the
eleven numbered items in §8; it is called out here because it materially affects sequencing.

## Statement

Planning/inventory document only. No deployment, no migration application, no feature-gate
enablement, no runtime validation, no implementation PR authorized or performed by this stage.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
