# AT-D28 — AT-M3.6B.2 Runtime Image Alignment authorization

> **Product Owner decision record. Authorizes ONE bounded internal non-production deployment
> action: rebuilding and redeploying the test-runtime orchestrator container from canonical `main`
> so the deployed code actually matches the repository, satisfying the
> `REQUIRED_BEFORE_REAL_SECRET_PROVISIONING_OR_LIVE_VALIDATION` prerequisite AT-D27 section 4
> recorded. It authorizes NO real Anthropic key, NO diagnostic or real external call, NO live-gate
> enablement, NO credential validation, NO AT-M3.6B.2 Live Validation, NO AT-M4, NO production
> action and NO HumanApproval mutation. `production_executed_true_count: 0`.**

```text
AT-D28:                      RESOLVED / BINDING
Recorded_on:                 2026-09-08
Recorded_by:                 Product Owner
Canonical_main_at_decision:  12eda4f7b4743293e0de3798652ce637f61e5edb
Branch:                      at-m3.6b.2-runtime-image-alignment-1
Depends_on:                  AT-D26 (docs/decisions/at-d26-at-m3-6b-2-runtime-secret-readiness-authorization.md)
                             AT-D27 (docs/decisions/at-d27-at-m3-6b-2-runtime-secret-readiness-acceptance-and-merge-authorization.md)
```

## 1. What this record is for

AT-D27 section 4 recorded a binding prerequisite: the internal test orchestrator image, independently
confirmed during Independent Validation 1 to predate AT-M3.6B.1, does not contain
`shared.sdk.agent_reasoning` and cannot execute the reasoning path the Vault rail is wired for. This
record authorizes closing exactly that gap — rebuilding and redeploying the orchestrator from
canonical code — and nothing else.

## 2. Authorized scope

```text
Internal non-production test runtime ONLY (compose project aiagents-test on the test host)
Orchestrator image rebuild/redeploy ONLY -- from canonical main 12eda4f, unmodified build mechanism
Preserve Vault initialization, seal state, storage volume and the scoped runtime token unchanged
Preserve Postgres/Redis data and audit state unchanged
The Anthropic secret at the canonical Vault path remains the non-callable placeholder throughout
REASONING_LIVE_NETWORK_ENABLED remains false throughout
Zero real or diagnostic Anthropic calls at any point in this stage
```

## 3. What is NOT authorized

```text
Real ANTHROPIC_API_KEY provisioning     NOT AUTHORIZED
Any real or diagnostic Anthropic call   NOT AUTHORIZED
Enabling the live network gate          NOT AUTHORIZED, not even briefly, not even to verify
Credential validation of any kind       NOT AUTHORIZED
AT-M3.6B.2 Live Validation               NOT AUTHORIZED -- this record prepares the runtime for a
                                           future authorization; it does not grant one
AT-M4 implementation                    NOT AUTHORIZED
Production action                       NOT AUTHORIZED
Production authorization                NOT GRANTED -- unchanged
HumanApproval mutation                  NOT AUTHORIZED
Vault re-initialization or data reset   NOT AUTHORIZED -- Vault state must survive this stage intact
A second secret-management authority    NOT AUTHORIZED
Any change to shared/, apps/, agents/,  NOT AUTHORIZED beyond what this record's own scope requires
  migrations/ business logic              -- see section 2; a Dockerfile/build-context defect found
                                           and fixed during this stage is the only exception, and
                                           only if strictly necessary to make canonical code
                                           deployable
```

## 4. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B.2 Live Validation, or any part of it
Does NOT authorize a real external call of any kind, official or diagnostic
Does NOT authorize enabling REASONING_LIVE_NETWORK_ENABLED
Does NOT authorize provisioning, reading, validating or exercising a real Anthropic credential
Does NOT authorize AT-M4 or any real work execution
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT amend AT-D26 or AT-D27
Does NOT dispose of HAZARD_AT_M3_LIVE_DENYLIST
Does NOT claim the runtime is production-ready in any respect
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
