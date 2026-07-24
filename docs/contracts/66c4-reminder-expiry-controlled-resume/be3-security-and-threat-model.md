# Step 66C.4-BE3-P — Security Requirements and Threat Model

> **Planning/contract document only. No security code implemented.**

## A. Security requirements (binding for BE3 implementation)

```text
1. Team isolation: every resume/replay resource is scoped to its team/project; cross-team access is
   impossible and non-existence is 404-masked (never 403) so existence is not leaked.
2. Project/resource ownership check: the resource's task/project ownership is verified before any
   state read that could reveal existence, and before any state change.
3. Operator/Approver separation: for replay, the requesting principal MUST NOT be the authorizing
   principal (two-person control); enforced at the authorize endpoint (403 two_person_required).
4. Production-approval separation: a production-effect task requires the separate production approval
   gate in addition to resume/replay authorization; no role bypasses it.
5. Service-identity scope: the Service Identity may only EXECUTE a command carrying a valid,
   unexpired, unconsumed, state-version-matching authorization; it can never request or authorize.
6. Authorization expiry: authorizations are time-bounded (expires_at) and single-use (consumed_at);
   expired or consumed authorizations are unusable.
7. Replay abuse prevention: only a 'dead' row may be replayed; attempts are never reset; a replayed
   row cannot be re-replayed without a new request+authorization; downstream dedupe via idempotency_key.
8. Rate limiting: resume/replay request + authorize endpoints are rate-limited per principal and per
   resource to bound a request/replay storm.
9. Reason-code allowlist: decision_reason_code is a bounded enum allowlist; never free text.
10. No raw clarification/answer content in any audit/event payload (reuse the existing
    safe_workroom_refs allowlist projection).
11. No secret/token/DSN/connection string in any authorization record, audit payload, log, or
    health/status response.
```

## B. Threat analysis

```text
T1. Requester authorizes own request (privilege bypass)
    -> Mitigation: replay requires requester_principal != approver_principal (two-person, D2); resume
       non-production authorization is the automated policy check (no self-fiat). 403 two_person_required.
T2. Stolen operator session (session compromise)
    -> Mitigation: two-person control for replay limits blast radius; production-effect still needs the
       separate production approval; authorizations are single-use + time-bounded; rate limiting; every
       action is durably audited with principal attribution for detection/forensics.
T3. Replay storm (flood of replay requests/executions)
    -> Mitigation: per-principal + per-resource rate limiting; only 'dead' rows are eligible; single-use
       authorization; idempotency_key dedupe downstream; replay executes via the internal adapter only.
T4. Stale authorization (resource changed after authorization)
    -> Mitigation: state-version-bound authorization + re-check at execution; a changed resource/policy
       version invalidates the authorization (409 resource_state_changed); no side effect on abort.
T5. Resource moved to another team after authorization
    -> Mitigation: ownership re-checked at execution; team change invalidates the authorization
       (state-version + ownership check); 404-masked to a caller who no longer owns it.
T6. Task canceled after authorization
    -> Mitigation: task-terminal re-check at execution time; canceled/aborted/terminal unconditionally
       blocks execution (decision effectively void); no dead->pending flip, no resume dispatch.
T7. Policy bypass at execution
    -> Mitigation: the orchestrator/executor re-checks the durable authorization + policy_result before
       any effect; execution never re-derives its own permission; a missing/invalid authorization aborts.
T8. Evidence tampering / content leak
    -> Mitigation: reason-code allowlist; safe_workroom_refs projection; no raw content/secret/DSN in
       evidence; audit rows are append-only through the existing audit path.
```

Severity posture for BE3 implementation review: any of {self-authorize bypass, missing durable
authorization, policy bypass at execution, raw-content/secret leak, public replay endpoint} is a
BLOCKING (critical/high) finding. A missing rate limit or a too-broad reason-code set is at least a
future-activation-blocking medium.

## Statement

Planning/contract document only. No security code implemented. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
