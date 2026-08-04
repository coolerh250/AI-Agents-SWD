# Step 66C.4-BE3-RA-2 — Implementation Stage Decomposition

> **Proposed decomposition only. NO stage below is authorized, scheduled, or started. Every stage
> requires its own separate, explicit Product Owner authorization, and every stage is additionally
> blocked on the Product Owner decisions it depends on. NO identity created, NO secret read or
> written, NO implementation performed by this stage. `production_executed_true_count: 0`.**

## 1. Dependency-driven reordering (and why)

§27 lists candidate stages in the order RA-2I1 … RA-2I6, RA-2R. That ordering is **not** dependency
correct, and this decomposition reorders it. The reasons are drawn from the code-verified inventory:

```text
Reorder 1 -- Secret backend/delivery must come BEFORE the authenticators that depend on it.
  RA-2I3 (Policy Authority credential delivery) and RA-2I2 (Service Identity) both need somewhere
  to put a key or credential. Building them first would force an interim env-var credential --
  i.e. re-creating the exact pattern (T-08) the work exists to remove. RA-2I4 therefore moves
  BEFORE RA-2I2 and RA-2I3.

Reorder 2 -- Operator identity (RA-2I1) stays first among the authenticators.
  It closes all three CRITICAL threats (T-01, T-02, T-03), it is a hard precondition for the
  two-person replay control to mean anything, and RA2-D12's proposed activation ordering starts
  with the API-only boundary that this stage enables.

Reorder 3 -- Service Identity (RA-2I2) moves AFTER Policy Authority (RA-2I3).
  Service Identity is the only one of the two that makes an EXECUTION path reachable. Policy
  Authority authentication changes an already-existing, already-gated decision path and creates no
  new execution capability, so it is the safer of the two to land first. RA2-D12 orders the
  activation boundary the same way (authority before service identity).

Reorder 4 -- Rotation/revocation (RA-2I5) cannot be a late add-on for the mechanisms, but its
  OPERATIONAL controls (break-glass, propagation SLA rehearsal) do belong after the credentials
  exist. It is therefore SPLIT: the per-credential lifetime/rotation properties are built into
  RA-2I3/I2 as acceptance criteria, and RA-2I5 covers only the cross-cutting operational controls.

Reorder 5 -- Identity audit/visibility (RA-2I6) also absorbs the production-approval grant path,
  which the inventory showed has zero callers and no endpoint. That is a genuine build item and it
  belongs with the operator-facing surface work, not with the authenticators.
```

### Proposed dependency-correct order

```text
RA-2I0  Identity Foundation Prerequisites        (new -- see §3)
RA-2I4  Secret Backend and Workload Delivery Integration
RA-2I1  Operator Identity Foundation
RA-2I3  Policy Authority Authentication and Credential Delivery
RA-2I2  Service Identity Authenticator Foundation
RA-2I5  Rotation, Revocation and Break-glass Controls
RA-2I6  Identity Audit, Admin Visibility and Production-Approval Grant Path
RA-2R   Combined Identity and Secret Security Review
```

`RA-2I0` is proposed as an addition because three hardening items are (a) genuinely independent of
every open Product Owner decision, (b) small, and (c) risk-reducing on their own — so they need not
wait for the decision package to be answered.

---

## 2. Stage records

### RA-2I0 — Identity Foundation Prerequisites *(proposed addition, decision-independent)*

```text
Objective:              Remove three concrete weaknesses that no open decision affects: (1) route
                        BE3 credential reads through the existing SecretRef wrapper instead of raw
                        os.environ; (2) remove the silent ephemeral-session-key fallback for any
                        non-dev environment and fail closed instead; (3) mirror the Admin Console's
                        test/production auth interlock onto the task/BE3 surface so
                        TASK_API_TEST_AUTH_ENABLED cannot be true under a production-like marker.
Required PO decisions:  NONE -- deliberately scoped to be decision-independent.
Allowed files:          apps/orchestrator/src/task_api.py, apps/orchestrator/src/operations_resume_api.py,
                        shared/sdk/operator_actions/session.py, plus tests.
Migration impact:       none.        Secret impact: no new secret; reduces exposure of existing ones.
Runtime impact:         none (no new capability; stricter fail-closed behaviour only).
Deployment impact:      none.
Verification level:     HIGH -- authentication-adjacent implementation + independent security review.
Independent review:     REQUIRED (touches authentication and secret-handling code paths).
Rollback:               revert the commit; behaviour returns to today's.
Activation boundary:    none -- no capability is activated; this stage only tightens fail-closed.
Threats addressed:      T-08 (partial), T-17, T-12 (session-key half).
```

### RA-2I4 — Secret Backend and Workload Delivery Integration

```text
Objective:              Stand up the chosen secret backend and the chosen delivery mechanism, and
                        move existing credentials onto it -- without introducing any new identity.
Required PO decisions:  RA2-D06 (backend), RA2-D07 (delivery), RA2-D08 (provisioning owner),
                        RA2-D11 (which environment first). BLOCKED until all four are answered.
Allowed files:          shared/sdk/secrets/*, infra/secrets/* (references only, never values),
                        infra/docker-compose/* or chart values as the chosen backend requires,
                        plus tests.
Migration impact:       none.
Secret impact:          HIGH -- this stage defines where every runtime secret lives. No real secret
                        value may enter git under any circumstance.
Runtime impact:         backend availability becomes a startup dependency; failure must fail closed.
Deployment impact:      YES -- new backend component and/or delivery mechanism.
Verification level:     CRITICAL if the target is a shared environment; HIGH if strictly isolated.
Independent review:     REQUIRED -- independent security review plus focused closure.
Rollback:               revert to the prior delivery for the affected credentials; destroy any
                        credentials issued during the attempt.
Activation boundary:    none -- no BE3 gate is enabled; no execution path becomes reachable.
Threats addressed:      T-06, T-08, T-13, T-18.
```

### RA-2I1 — Operator Identity Foundation

```text
Objective:              Replace header-asserted operator identity with a verified identity and a
                        server-side entitlement source, on BOTH operator surfaces, so that one
                        verified subject model serves the Admin Console and the BE3 APIs.
Required PO decisions:  RA2-D01, RA2-D02, RA2-D03. BLOCKED until all three are answered.
Allowed files:          apps/orchestrator/src/task_api.py (authenticator), operator_actions_api.py,
                        shared/sdk/identity/* (implement against the existing fail-closed
                        interfaces), shared/sdk/operator_actions/{auth,session,rbac}.py, tests.
Migration impact:       LIKELY -- an entitlement/role-binding table if RA2-D03 chooses a
                        platform-owned or hybrid model. Would follow the RA-1 migration process.
Secret impact:          session signing key and/or IdP client credential -- must come from RA-2I4.
Runtime impact:         every operator request path changes; must remain fail-closed.
Deployment impact:      IdP connectivity if RA2-D01 chooses an external provider.
Verification level:     HIGH -- operator authentication implementation + independent security review.
Independent review:     REQUIRED.
Rollback:               disable the new authenticator -> surface fails closed (today's default).
Activation boundary:    enables RA2-D12 Option A (API-only) and nothing beyond it.
Threats addressed:      T-01, T-02, T-03 (all CRITICAL), T-11, T-16, T-17.
```

### RA-2I3 — Policy Authority Authentication and Credential Delivery

```text
Objective:              Move the Policy Authority from a long-lived env-var bearer secret to the
                        chosen authenticated form, preserving every existing strength.
Required PO decisions:  RA2-D05, plus RA2-D06/D07 (delivery) and RA2-D09 (lifetime/rotation).
Must preserve:          constant-time comparison; dedicated-header-only sourcing; no short-circuit;
                        uniform 403; never logged/echoed; fixed role label; and above all the
                        CAPABILITY CONFINEMENT to authorize/reject only. A regression in any of
                        these is a blocking finding.
Must add:               expiry/audience/issuer (or equivalent), a BOUNDED rotation overlap, and a
                        principal identity derived from the verified credential rather than from
                        the client-supplied header.
Allowed files:          apps/orchestrator/src/operations_resume_api.py, a new authenticator module,
                        shared/sdk/secrets/*, tests.
Migration impact:       none expected.
Secret impact:          HIGH -- this is an authority-bearing credential.
Runtime impact:         changes an existing gated decision path; creates NO new execution path.
Deployment impact:      credential provisioning for the policy authority workload.
Verification level:     HIGH -- independent security review required.
Independent review:     REQUIRED.
Rollback:               clear the credential -> the authority path fails closed, exactly as today.
Activation boundary:    enables RA2-D12 Option B; still no execution path.
Threats addressed:      T-07, T-15, T-06, T-13.
```

### RA-2I2 — Service Identity Authenticator Foundation

```text
Objective:              Build the first real Service Identity authenticator so that a workload can
                        prove what it is, making the existing consume-only authorization branch
                        reachable by a genuine caller.
Required PO decisions:  RA2-D04, plus RA2-D06/D07 and RA2-D09. BLOCKED until answered.
Allowed files:          a new authenticator module under shared/sdk/tasks/ or apps/orchestrator/src/,
                        wiring at the consume call sites, tests.
Migration impact:       none expected.
Secret impact:          HIGH -- workload credential/key custody.
Runtime impact:         HIGHEST OF ANY STAGE HERE -- this is the first stage after which an
                        execution path has an authenticated caller. Note it does NOT by itself
                        build the missing consumer; that remains separate work.
Deployment impact:      credential/certificate/token issuance path for each workload.
Verification level:     HIGH, escalating to CRITICAL if combined with enabling any execution gate.
Independent review:     REQUIRED -- independent security review plus focused closure.
Rollback:               disable the authenticator and the consume path -> fails closed; the
                        execution gates remain independently default-false.
Activation boundary:    enables RA2-D12 Option C. MUST NOT be reached while operator identity is
                        still header-asserted (explicit constraint from RA2-D12).
Threats addressed:      T-04, T-05, T-16.
```

### RA-2I5 — Rotation, Revocation and Break-glass Controls

```text
Objective:              Operationalize the lifecycle: bounded rotation windows with alerting, a
                        measured revocation-propagation SLA, and (if authorized) a controlled
                        break-glass path.
Required PO decisions:  RA2-D09, RA2-D10, RA2-D08.
Allowed files:          operational tooling under scripts/, posture/alerting configuration,
                        documentation, tests. No new authentication logic.
Migration impact:       none.
Secret impact:          MODERATE -- rehearsals must use disposable credentials only.
Runtime impact:         rotation/revocation rehearsals against the validation environment only.
Deployment impact:      alerting rules.
Verification level:     HIGH -- includes a real rotation and a real revocation rehearsal with
                        measured propagation time.
Independent review:     REQUIRED for the break-glass component specifically.
Rollback:               remove the break-glass path; revert alerting.
Activation boundary:    none.
Threats addressed:      T-11, T-12, T-13, T-14.
Explicit constraint:    NO real break-glass credential may be created without its own separate
                        Product Owner authorization.
```

### RA-2I6 — Identity Audit, Admin Visibility and Production-Approval Grant Path

```text
Objective:              Make identity decisions and approval requests visible and actionable:
                        identity-aware audit records, an operator-facing evidence surface, and the
                        production-approval grant/revoke path that currently has NO endpoint and
                        ZERO callers.
Required PO decisions:  RA-P items 1, 2, 10 (grant-path owner; approval visibility; required
                        Admin Console evidence) -- i.e. RA2-D08 plus the RA6-deferred items.
Allowed files:          apps/orchestrator/src/ (a new approval endpoint + posture/evidence surface),
                        apps/admin-console/src/, shared/sdk/tasks/production_approval_service.py
                        callers, tests.
Migration impact:       none expected (migration 035 already provides the registry).
Secret impact:          none new -- but this surface must never render a credential value.
Runtime impact:         creates the first real path by which a human can grant a production
                        approval, which is a security-material capability in its own right.
Deployment impact:      Admin Console rebuild.
Verification level:     HIGH -- the grant path directly gates production-effect resume.
Independent review:     REQUIRED.
Rollback:               remove the endpoint/surface; the registry remains inert.
Activation boundary:    does not itself enable execution, but it is a precondition for any
                        production-effect resume ever being legitimately approvable.
Threats addressed:      T-09, T-19, T-20 (audit half).
```

### RA-2R — Combined Identity and Secret Security Review

```text
Objective:              One independent security review across every identity/secret stage that
                        actually shipped, re-deriving the guarantees end-to-end rather than
                        per-stage.
Required PO decisions:  none new -- but it can only run after the stages it reviews.
Allowed files:          review artifacts on a review branch only; NO implementation modification.
Migration impact:       none.   Secret impact: none (review must not read real secrets).
Runtime impact:         none.   Deployment impact: none.
Verification level:     CRITICAL -- independent reviewer, own worktree, own ephemeral environment,
                        following the RA-1R/RA-1FC pattern proven across RA-1.
Independent review:     THIS STAGE IS THE INDEPENDENT REVIEW.
Rollback:               n/a.
Activation boundary:    none -- a review authorizes nothing.
Required scope:         the full chain operator -> authority -> service identity; credential
                        lifetime/rotation/revocation; no-leak proofs; and confirmation that the
                        capability confinement and scope-isolation guarantees still hold.
```

---

## 3. Risk-based verification plan (§28 classification applied)

```text
Documentation/decision-only  -> self-check + deterministic verifier
    RA-2 itself (this stage). No runtime implementation exists to review, so per §28 NO
    independent implementation review is performed or required here.

Operator authentication implementation -> HIGH: implementation + independent security review
    RA-2I1; RA-2I0 (authentication-adjacent).

Service Identity implementation -> HIGH: implementation + independent security review
    RA-2I2.

Policy Authority credential delivery -> HIGH: implementation + independent security review
    RA-2I3.

Secret backend integration -> HIGH or CRITICAL depending on environment
    RA-2I4: HIGH if strictly isolated/ephemeral; CRITICAL if a shared environment is the target.

Shared activation -> CRITICAL: independent review + focused closure + PO gate
    Any stage that enables a BE3 feature gate in a shared runtime. NONE of the stages above does
    this; activation remains a separate, later, explicitly authorized step.
```

## 4. Earliest executable stage

```text
Earliest executable WITHOUT any further Product Owner decision:
    RA-2I0 (Identity Foundation Prerequisites) -- deliberately scoped to be decision-independent.
    It still requires its own explicit Product Owner authorization to start.

Earliest executable AFTER decisions:
    RA-2I4, once RA2-D06, RA2-D07, RA2-D08 and RA2-D11 are answered.

BLOCKED until decisions are made:
    RA-2I1 (needs D01/D02/D03), RA-2I3 (needs D05 + D06/D07/D09),
    RA-2I2 (needs D04 + D06/D07/D09), RA-2I5 (needs D09/D10/D08),
    RA-2I6 (needs D08 + RA-P items 1/2/10).
```

## 5. Standing constraints on every stage above

```text
No stage may be started without its own separate, explicit Product Owner authorization.
No stage may apply a shared migration, deploy, enable a BE3 feature gate, start a
  poller/relay/worker/consumer, or execute resume/replay/dispatch.
No stage may create a break-glass credential without separate authorization.
No runtime agent may provision its own authority identity or credential, in any stage, ever.
No real secret value may be committed to git in any stage.
production_executed_true_count must remain 0 until a Product-Owner-authorized activation stage.
```

## 6. Posture

```text
RA-2: DECISION PACKAGE COMPLETE | CURRENT STATE INVENTORIED | THREAT MODEL COMPLETE
      IMPLEMENTATION STAGES PROPOSED | PRODUCT OWNER DECISIONS PENDING
      NO IDENTITY PROVISIONED | NO SECRET READ OR WRITTEN | NO RUNTIME IMPLEMENTATION
      NO DEPLOYMENT | NO ACTIVATION
Proposed stages: 8 (RA-2I0, RA-2I4, RA-2I1, RA-2I3, RA-2I2, RA-2I5, RA-2I6, RA-2R)
Authorized stages: 0
RA-3 and every implementation stage: NOT AUTHORIZED
Gates 1/2/6 (RA-1): PENDING RUNTIME/SHARED EXECUTION -- unchanged by this stage
production_executed_true_count: 0
Next authorization required: Product Owner answers to the 12 decisions in the decision package,
  then explicit authorization for whichever implementation stage is to run first.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
