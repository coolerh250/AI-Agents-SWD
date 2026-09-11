# AT-D42 — AT-M3.6B.2 Critique Safe Diagnostic Runtime Image Redeploy authorization

> **Product Owner decision record. Authorizes ONE bounded internal non-production deployment
> action: rebuilding and redeploying the test-runtime orchestrator container from canonical `main`
> (containing the AT-D41-accepted diagnostic-capture remediation, `767c5b1`) so the deployed code
> actually contains the safe `ValidationError` diagnostic capability. It authorizes NO application
> code change, NO DB migration, NO budget-policy activation, NO live-gate enablement, NO credential
> read/rotation, NO real or diagnostic Anthropic call, NO AT-M3.5, NO AT-M4, NO HumanApproval
> mutation, and NO production action. `production_executed_true_count: 0`.**

```text
AT-D42:                      RESOLVED / BINDING
Recorded_on:                 2026-09-11
Recorded_by:                 Product Owner
Canonical_main_at_decision:  05a80f65e015204c8086ce166488cafa9ec57277
Accepted_implementation:     767c5b149ae8090345267ce83a0d39292618f50b
Depends_on:                  AT-D38 (docs/decisions/at-d38-at-m3-6b-2-runtime-image-redeploy-evidence-reconciliation.md)
                             AT-D40 (docs/decisions/at-d40-at-m3-6b-2-critique-validationerror-safe-diagnostic-metadata-remediation-authorization.md)
                             AT-D41 (docs/decisions/at-d41-at-m3-6b-2-critique-validationerror-safe-diagnostic-metadata-product-acceptance-and-merge-authorization.md)
```

## 1. What this record is for

AT-D41 accepted and fast-forward merged the AT-D40-authorized diagnostic-capture remediation to
`main`. The deployed internal test-runtime orchestrator image predates that merge and does not
contain it. This record authorizes closing exactly that gap — rebuilding and redeploying the
orchestrator from canonical code — and nothing else. It does not authorize retrying the critique call
the capability applies to.

## 2. Authorized scope

```text
Internal non-production test runtime ONLY (compose project aiagents-test on the test host)
Orchestrator image rebuild/redeploy ONLY -- from canonical main 05a80f6 (containing 767c5b1),
    unmodified build mechanism
Preserve Vault initialization, seal state, storage volume and the scoped runtime token unchanged
Preserve Postgres data, including the historical AT-D32 accounting rows, unchanged
Preserve budget policy d29ad073-9f7c-48b4-876d-cd3cb1343b40 in its current inactive status --
    no activation, no deactivation-then-reactivation cycle
REASONING_LIVE_NETWORK_ENABLED remains false throughout
Zero real or diagnostic Anthropic calls at any point in this stage
```

## 3. What is NOT authorized

```text
Application code change of any kind          NOT AUTHORIZED -- deploy exactly what AT-D41 accepted
A DB migration                               NOT AUTHORIZED -- schema already aligned per AT-D34
Any real or diagnostic Anthropic call        NOT AUTHORIZED
Enabling the live network gate               NOT AUTHORIZED, not even briefly, not even to verify
Reactivating the budget policy               NOT AUTHORIZED -- a future critique-only Live Validation
                                                needs its own separate authorization for that
Credential read, validation, or rotation     NOT AUTHORIZED
A critique-only Live Validation attempt      NOT AUTHORIZED -- this record prepares the runtime for a
                                                future authorization; it does not grant one
Rerunning propose/replay/decompose_plan/     NOT AUTHORIZED -- their AT-D39 PASS results stand and are
    summarize_decision against the provider     not to be reopened by this stage
AT-M4 implementation                          NOT AUTHORIZED
Production action                             NOT AUTHORIZED
Production authorization                      NOT GRANTED -- unchanged
HumanApproval mutation                        NOT AUTHORIZED
Recreating Postgres, Vault, or any other      NOT AUTHORIZED unless Compose mechanically requires it
  healthy dependency service                    and it is demonstrated non-destructive
Overwriting AT_M3_6B_2_RUNTIME_IMAGE          NOT AUTHORIZED -- that field records the separate,
                                                already-closed AT-D38 redeploy and stays as-is
```

## 4. Preserved historical state

```text
AT-D32 real requests consumed:      5 of 12 (unchanged)
AT-D32 real requests remaining:     7 (unchanged)
Retained unresolved reservation:    US$0.016086 (unchanged)
Effective AT-D32 validation cost:   US$0.060134 (unchanged)
Budget policy:                      inactive (unchanged)
Live gate:                          false (unchanged)
production_executed_true_count:     0 (unchanged)
propose / replay / decompose_plan / summarize_decision:  PASS, not reopened by this stage
critique:                           TERMINAL, unretried malformed_output
                                     (correlation_id 65496538-621c-4c22-99e0-f510507b358f)
```

## 5. Execution and evidence

The redeploy itself — build, recreate, in-container zero-network diagnostic proof, and health/state
verification — is performed as a separate execution step under this authorization and reported in
`AT-M3.6B.2-CRITIQUE-SAFE-DIAGNOSTIC-RUNTIME-IMAGE-REDEPLOY-1`. Per that report's own governance
note, this authorization record does NOT itself grant authority to reconcile the resulting runtime
evidence back into `AI_AGENTS_PM_STATE.md`/`source/progress.md` — a separate decision, closing the
loop on the deployed evidence, is expected next.

## 6. Next decision

`AT-M3.6B.2 Critique Runtime Redeploy Evidence Reconciliation` — canonicalizing the redeploy
execution's reported evidence (deployed source SHA, in-container sanitizer proof, request-contract
non-regression, health/schema/Vault/budget/live-gate state) into `AI_AGENTS_PM_STATE.md` and
`source/progress.md`. Separately, and not granted by this record: a fresh, critique-only, bounded
Live Validation authorization (policy activation → one critique call → terminal policy deactivation)
under AT-D32's remaining envelope (7 of 12 requests).

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
