# Step 66C.4-BE3-RA-P → Runtime Activation Stage Sequence (Handoff)

> **Proposed sequence only. Nothing below is authorized to start by this document. Each stage
> requires its own separate, explicit Product Owner authorization. The candidate names in the
> original planning prompt (RA-1..RA-11) were a starting point only; this sequence is reordered and
> re-scoped against the actual dependencies found during Step 66C.4-BE3-RA-P (see
> `be3-runtime-activation-readiness-plan.md`, especially §4's finding that no runtime-callable
> caller or consumer exists for either resume-command or replay-execution today).**

## Why this differs from the candidate list

The candidate list proposed one combined "Audit Relay Runtime Validation" stage and one combined
"Resume Command Consumer Foundation" / "Replay Execution Runtime Foundation" pair. Investigation
found:

- Resume-command activation needs **two** new runtime pieces (a Service-Identity-authenticated
  caller of `prepare_execution`, AND a downstream consumer of the `resume.execution_requested`
  outbox row that dispatches to `ResumeEngine`) because BE3-B intentionally split "consume and
  write a durable command" from "execute the command."
- Replay-execution activation needs only **one** new runtime piece (a Service-Identity-
  authenticated caller of `execute_authorized_replay`), because BE3-C's adapter consumes the
  authorization and performs the replay synchronously in the same transaction -- there is no
  outbox-command intermediary for replay.
- Identity/secret provisioning (Policy Authority credential delivery, Service Identity
  authentication, canonical operator identity source) is a genuine product decision blocking BOTH
  the resume and replay foundations, so it is pulled out as its own stage rather than folded into
  either.

## Proposed sequence

### RA-1 — Shared Migration Rehearsal and Rollback Proof

```text
Capability:          apply migrations 031+032+033+034+035, in sequence, to a disposable runtime
                      that mirrors the shared stack's PostgreSQL version/config, then roll all five
                      back in reverse order, proving zero data loss both directions.
Closes gates:         1, 2, 6 (readiness plan §5).
Independently
  verifiable:         row/index/constraint existence checked before/after apply; row counts
                      unchanged by rollback; a pre-seeded "existing row" (mimicking real
                      clarification/task data) survives apply+rollback unmutated.
Rollback:             this stage IS the rollback rehearsal; the disposable runtime is destroyed
                      after, regardless of outcome.
Authorization
  boundary:           runs ONLY on a disposable/isolated runtime, never the shared aiagents-test
                      stack; requires PO decision on which disposable runtime to use (readiness
                      plan §7 item 6, reused here).
Risk tier:            HIGH (migration) -> implementation flow + single independent
                      security/transaction review.
```

### RA-2 — Identity and Secret Provisioning Decision

```text
Capability:          resolve the product decisions that block every later stage: canonical operator
                      identity source, Service Identity authentication mechanism, Policy Authority
                      secret delivery mechanism (readiness plan §7 items 3-5). Output is a decision
                      record, not running code.
Closes gates:         7 (reinterpreted for BE3), contributes to 8, 11.
Independently
  verifiable:         a written decision record citing exactly which existing mechanism
                      (env-var principal id + rotating capability header, per
                      apps/orchestrator/src/operations_resume_api.py) will be provisioned, by whom,
                      and through which secret store.
Rollback:             n/a (decision record; no runtime change).
Authorization
  boundary:           Product Owner decision required before RA-3/RA-4/RA-5 may be scoped in
                      detail; this stage does not itself touch any secret store or runtime.
Risk tier:            LOW in isolation (documentation only) -> self-check + deterministic verifier.
                      Note: the decision itself feeds every later HIGH/CRITICAL stage (RA-4, RA-5,
                      RA-6, RA-9..RA-12), so getting it wrong has outsized downstream consequence
                      even though this stage's own activity is not itself risky.
```

### RA-3 — BE2 Audit-Path Activation Decision

```text
Capability:          decide (per readiness plan §8's cross-cutting note) whether BE3's audit
                      evidence delivery activates the existing BE2 poller/relay (Gates 3-4) or a
                      narrower BE3-scoped path; if the former, deploy+health/metrics-verify the BE2
                      poller and relay in the target runtime (audit destination ONLY, still no BE3
                      gate flipped).
Closes gates:         3, 4, contributes to 9.
Independently
  verifiable:         poller/relay health endpoints respond; a synthetic (non-BE3) reminder/expiry
                      event flows through end-to-end in the target runtime; metrics visible in the
                      existing Prometheus/Grafana stack.
Rollback:             stop the two services; no BE3 schema or gate touched; BE2's own migration 031
                      rollback already proven in RA-1.
Authorization
  boundary:           this activates BE2 capability, not BE3 -- requires its own explicit PO
                      authorization distinct from any BE3 gate, since it revives a stage (BE2) that
                      was deliberately left NOT ACTIVATED at BE2-M.
Risk tier:            MEDIUM (isolated runtime adapter, health endpoints, no authorization consume)
                      -> self-check + targeted verifier.
```

### RA-4 — Resume Command Consumer Foundation

```text
Capability:          build (a) a Service-Identity-authenticated internal caller of
                      resume_service.prepare_execution, and (b) a new consumer that claims
                      DESTINATION_ORCHESTRATOR_COMMAND outbox rows and dispatches
                      resume.execution_requested to ResumeEngine.resume_workflow, with the same
                      bounded retry/backoff/dead semantics BE2-R1 proved for the audit destination.
Closes gates:         5 (command-destination half), 10 (resume half), the "command
                      acknowledgement/idempotency" and "Service Identity authentication" standalone
                      areas.
Independently
  verifiable:         a synthetic pending resume.execution_requested row is claimed exactly once,
                      dispatched, and marked published; a forced dispatch failure retries per the
                      existing backoff schedule and eventually reaches dead with no duplicate
                      workflow resume.
Rollback:             the new consumer is a separate deployable; stopping it leaves durable
                      resume_requests/authorizations/outbox rows untouched (no in-flight mutation
                      lost, per BE3-B's transaction design).
Authorization
  boundary:           new implementation, not merely activation -- requires a scoped implementation
                      authorization (this is new code, following this project's standard
                      implementation-authorization pattern) before any commit, separate from
                      turning BE3_RESUME_COMMAND_ENABLED on.
Risk tier:            HIGH (consumer concurrency, command delivery) -> implementation flow + single
                      independent security/transaction review.
```

### RA-5 — Replay Execution Runtime Foundation

```text
Capability:          build a Service-Identity-authenticated internal caller of
                      replay_service.execute_authorized_replay. No separate consumer is needed
                      (the adapter already consumes the authorization and performs the replay
                      synchronously in one transaction, per BE3-C).
Closes gates:         10 (replay half), contributes to the "Service Identity authentication"
                      standalone area (shared mechanism with RA-4).
Independently
  verifiable:         a synthetic granted replay authorization, invoked through the new caller,
                      transitions the target dead row to pending exactly once; a repeat call against
                      the same (now single-used) authorization is rejected, not re-executed.
Rollback:             the new caller is a thin internal entrypoint; removing/disabling it leaves the
                      existing replay_dead_row transaction semantics (already proven) untouched.
Authorization
  boundary:           new implementation authorization required, separate from
                      BE3_REPLAY_EXECUTION_ENABLED.
Risk tier:            HIGH (replay execution) -> implementation flow + single independent
                      security/transaction review.
```

### RA-6 — Production Approval Grant Path

```text
Capability:          a real, RBAC-gated way for reviewer_approver/platform_admin to grant/revoke a
                      production_action_approvals row at runtime (an internal-only endpoint or
                      Admin Console action -- shape depends on readiness plan §7 items 1-2, still
                      open).
Closes gates:         the "production approval grant lifecycle (runtime-facing half)" standalone
                      area.
Independently
  verifiable:         only reviewer_approver/platform_admin can grant; a Service Identity or any
                      other role is rejected; a granted approval is immediately resolvable by the
                      existing (unmodified) resolve_and_consume_approval.
Rollback:             the grant surface is additive; disabling it leaves already-granted approvals
                      resolvable exactly as today (no change to the resolver itself).
Authorization
  boundary:           new implementation authorization required; depends on RA-2's identity
                      decision (who the real reviewer_approver/platform_admin principals are).
Risk tier:            HIGH (creates real, consumable production-effect authority) -> implementation
                      flow + single independent security/transaction review.
```

### RA-7 — Metrics, Logs, Health and Runtime Reconciliation

```text
Capability:          add BE3-specific counters (requests/authorizations/consumes/rejections by
                      reason code) to shared/sdk/tasks/lifecycle_metrics.py's existing Prometheus
                      registration pattern; add a read-only reconciliation report for
                      pending-past-expiry resume/replay rows.
Closes gates:         the "metrics/logs/traces/health" and "runtime reconciliation" standalone
                      areas; contributes to Gate 9/10's observability requirement.
Independently
  verifiable:         new metrics appear in the existing Grafana dashboard set; the reconciliation
                      report correctly flags a seeded expired-but-unconsumed row and nothing else.
Rollback:             purely additive instrumentation; removing it has no functional impact.
Authorization
  boundary:           implementation authorization for new (non-security-critical) code.
Risk tier:            MEDIUM (metrics, health endpoints) -> self-check + targeted verifier.
```

### RA-8 — Disabled Runtime Deployment

```text
Capability:          deploy the current BE3 code (all four feature gates still false) to a
                      shared-like test runtime, with migrations 031-035 applied per RA-1's proven
                      procedure. Zero behavior change from today's disabled state; this stage proves
                      the deployment itself is inert.
Closes gates:         contributes to Gate 10's precondition (code + schema present before any gate
                      flip).
Independently
  verifiable:         every BE3 endpoint returns its existing disabled-by-default response; no
                      resume/replay row is ever created; health checks pass.
Rollback:             redeploy the prior image; migrations already proven reversible at RA-1.
Authorization
  boundary:           deployment authorization (distinct from any gate-enable authorization).
Risk tier:            MEDIUM (read-only deployment, no gate flipped) -> self-check + targeted
                      verifier.
```

### RA-9 — API-only Controlled Validation

```text
Capability:          flip BE3_RESUME_API_ENABLED and BE3_REPLAY_API_ENABLED ONLY (command/execution
                      gates remain false). Exercise create/authorize under the bounded event count
                      and allowed-event scope from readiness plan §7 items 7-8 (still open PO
                      decisions).
Closes gates:         8, 9 (runtime dimension), contributes to 10.
Independently
  verifiable:         every created request/authorization is durable and RBAC-correct; zero
                      resume/replay execution occurs (command/execution gates stay false
                      throughout); audit evidence (if RA-3 activated the relay) is delivered and
                      inspectable.
Rollback:             flip both gates back to false; no execution ever occurred, so no execution
                      state to unwind -- only durable request/authorization rows remain, which are
                      themselves inert without the command/execution gates.
Authorization
  boundary:           first SHARED-runtime exposure of BE3 -- explicit Product Owner gate required,
                      scoped to a hard cap on operations and a defined abort threshold (§7 items
                      8-9).
Risk tier:            CRITICAL (shared activation) -> independent review + focused closure +
                      explicit Product Owner gate.
```

### RA-10 — Command-path Controlled Validation

```text
Capability:          flip BE3_RESUME_COMMAND_ENABLED; exercise RA-4's consumer end-to-end under a
                      hard operation cap, using only the events approved for validation (§7 item 7).
Closes gates:         10 (resume half, completes it).
Independently
  verifiable:         a real (validation-scoped) resume request flows request -> authorize ->
                      command consume -> orchestrator dispatch -> confirmation, exactly once per
                      request, with the durable audit trail intact.
Rollback:             flip the gate back to false; stop the RA-4 consumer; any in-flight command
                      remains a durable, re-inspectable outbox row (no silent loss per the retry/DLQ
                      design).
Authorization
  boundary:           explicit Product Owner gate, separate from RA-9's.
Risk tier:            CRITICAL (production-effect path, first real dispatch) -> independent review +
                      focused closure + explicit Product Owner gate.
```

### RA-11 — Replay-path Controlled Validation

```text
Capability:          flip BE3_REPLAY_EXECUTION_ENABLED; exercise RA-5's caller end-to-end under the
                      existing per-event (3) and per-actor rate caps, using only validation-approved
                      events.
Closes gates:         10 (replay half, completes it).
Independently
  verifiable:         a real (validation-scoped) two-person-authorized replay moves a dead row to
                      pending exactly once; a repeat attempt against the same authorization is
                      rejected; the per-event/per-actor caps are enforced under the real runtime's
                      concurrency, not just the isolated-container tests.
Rollback:             flip the gate back to false; stop the RA-5 caller path; replayed rows remain
                      in their new (pending) state -- this is an intentional, already-audited
                      mutation, not something to "undo" silently.
Authorization
  boundary:           explicit Product Owner gate, separate from RA-9/RA-10's.
Risk tier:            CRITICAL (production-effect path, first real replay) -> independent review +
                      focused closure + explicit Product Owner gate.
```

### RA-12 — Activation Go/No-Go Review

```text
Capability:          a consolidated review of everything exercised in RA-1 through RA-11 -- the
                      terminal gate (Gate 11 in the original 11-item list) before any wider rollout,
                      real (non-validation-scoped) workload, or additional runtime.
Closes gates:         11.
Independently
  verifiable:         the review reproduces (does not merely accept) the RA-9/10/11 evidence: caps
                      held, rollback thresholds never breached, audit trail complete, RBAC/scope
                      isolation intact under real concurrency.
Rollback:             a NO-GO stops everything at its current (already-bounded) state; nothing
                      further is authorized until remediated and re-reviewed.
Authorization
  boundary:           independent review + focused closure + explicit Product Owner gate -- the
                      same discipline already established for BE3-R/BE3-R-FC, applied here to
                      runtime activation instead of code-merge readiness.
Risk tier:            CRITICAL (irreversible operation boundary -- this is the last gate before BE3
                      capability is treated as "activated" rather than "validated under caps").
```

## Statement

Handoff/sequence-design record only. No stage above is started, authorized, or scheduled by this
document. Each requires its own separate, explicit Product Owner authorization, following the same
scoped-authorization discipline used throughout Step 66C.4-BE3.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
