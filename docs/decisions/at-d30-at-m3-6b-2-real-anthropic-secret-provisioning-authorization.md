# AT-D30 — AT-M3.6B.2 real Anthropic secret provisioning authorization

> **Product Owner decision record. Authorizes ONE bounded action: writing the Product Owner's real
> non-production Anthropic API key into the already-canonical Vault rail at
> `secret/aiagents/test-runtime`, field `ANTHROPIC_API_KEY`, via `vault kv patch`. It authorizes NO
> use of that credential against Anthropic — no live-gate enablement, no Messages API call, no
> credential-validity probe, no model-list call, no health probe, no pricing request, no diagnostic
> external call of any kind. It authorizes NO AT-M3.6B.2 Live Validation, NO AT-M4, NO production
> action and NO HumanApproval mutation. `production_executed_true_count: 0`.**

```text
AT-D30:                      RESOLVED / BINDING
Recorded_on:                 2026-09-08
Recorded_by:                 Product Owner
Canonical_main_at_decision:  04f4bc65931d1cbe3b9de6a7df62e5dbe64cac75
Branch:                      at-m3.6b.2-real-anthropic-secret-provisioning-1
Depends_on:                  AT-D26 (docs/decisions/at-d26-at-m3-6b-2-runtime-secret-readiness-authorization.md)
                             AT-D27 (docs/decisions/at-d27-at-m3-6b-2-runtime-secret-readiness-acceptance-and-merge-authorization.md)
                             AT-D28 (docs/decisions/at-d28-at-m3-6b-2-runtime-image-alignment-authorization.md)
                             AT-D29 (docs/decisions/at-d29-at-m3-6b-2-runtime-image-alignment-ratification-and-merge-authorization.md)

AT-M3.6B.2 RUNTIME SECRET READINESS:    CLOSED / CANONICAL
AT-M3.6B.2 RUNTIME IMAGE ALIGNMENT:     CLOSED / CANONICAL
AT-M3.6B.2 LIVE VALIDATION:             NOT AUTHORIZED
THIS SLICE:                             AUTHORIZED
REAL ANTHROPIC CALLS:                   0
DIAGNOSTIC EXTERNAL CALLS:               0
REASONING_LIVE_NETWORK_ENABLED:         false
AT-M4:                                   NOT AUTHORIZED
Production:                             NOT GRANTED
production_executed_true_count:         0
```

## 1. What this record is for

AT-D27 section 4 and AT-D29 both recorded the same standing boundary from opposite ends: real
secret provisioning and AT-M3.6B.2 Live Validation each require their own separate Product Owner
authorization, and neither is implied by the other or by the readiness/alignment work that precedes
them. AT-D29 closed the runtime-image-alignment gap, so the deployed test orchestrator now runs the
canonical reasoning adapter and reports a truthful safety surface — but the Vault field still holds
the placeholder, and the credential does not exist anywhere in this runtime.

This record authorizes exactly the next narrow step: writing the real key into the already-validated
Vault rail so the field is populated. It deliberately does **not** authorize using that credential
for anything. Preparing a credential and spending it are different risks, and collapsing them here
would repeat the exact pattern AT-D26 section 1 drew a line against for the rail itself.

## 2. Authorized scope

```text
Provisioning the real ANTHROPIC_API_KEY value into Vault KV v2
    mount   secret
    path    aiagents/test-runtime
    field   ANTHROPIC_API_KEY
    method  vault kv patch (never put -- preserves every other field at that path)
Opaque /dev/shm secret-file handoff for the credential itself (Claude Code receives a path, never
    a value)
Opaque /dev/shm operator-token-file handoff for Vault write authority, using the pattern already
    established by scripts/complete_vault_runtime_readiness.sh
Value-free verification that the field exists and is present/callable at the SecretProvider layer
Orchestrator cache refresh via `docker compose restart orchestrator` (secret-value-only change --
    the environment does not change, so --force-recreate is not required and is not authorized by
    this record for that reason)
```

## 3. What is NOT authorized

```text
REASONING_LIVE_NETWORK_ENABLED=true    NOT AUTHORIZED, not even briefly, not even to verify
Any Anthropic Messages API call        NOT AUTHORIZED
Any credential-validity probe          NOT AUTHORIZED
Any model-list call                    NOT AUTHORIZED
Any provider health probe              NOT AUTHORIZED
Any pricing request                    NOT AUTHORIZED
Any diagnostic external call           NOT AUTHORIZED -- the Step 65F-C guardrail is unchanged:
                                          every external call counts, diagnostic ones included
AT-M3.6B.2 Live Validation             NOT AUTHORIZED -- a separate, future Product Owner decision
                                          naming provider, model, call count, cost ceilings, allowed
                                          verbs, environment, gate enablement, credential use and
                                          abort conditions
AT-M4 implementation                   NOT AUTHORIZED
Production action                      NOT AUTHORIZED
Production authorization               NOT GRANTED -- unchanged
HumanApproval mutation                 NOT AUTHORIZED
Widening the scoped runtime token's    NOT AUTHORIZED -- the runtime keeps its read-only,
    privileges                           single-path policy; only operator/root authority may write
A second secret-management authority   NOT AUTHORIZED
Rendering the credential value at any  NOT AUTHORIZED -- not to a terminal, a log, a test fixture,
    point in this procedure               an audit row, or this conversation
```

## 4. Handling contract

```text
The real API-key value NEVER appears in: argv, an environment variable this process exports,
    process listings (ps), a log line, a git diff, a test fixture, an audit record, or this
    conversation's transcript.
The secret file and the operator-token file are each validated BEFORE being read one byte: must
    exist, be a regular file, not a symlink, owned by the invoking user, mode 600 or stricter, and
    outside the repository working tree -- the same contract
    scripts/complete_vault_runtime_readiness.sh already enforces for the operator-token handoff.
The value travels file -> shell variable -> child-process environment (docker compose exec -T -e)
    -> Vault, on stdin where the Vault CLI supports it, never as a CLI argument.
On a successful write and successful value-free verification, the secret file is deleted
    (source_file_removed=yes). On failure, it is retained (source_file_removed=no) -- this record
    does not authorize silently destroying the operator's only copy of a credential that did not
    get where it was going.
The operator-token file is deleted once Vault write authority is no longer needed, on the same
    success/failure discipline.
```

## 5. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B.2 Live Validation, or any part of it
Does NOT authorize a real external call of any kind, official or diagnostic
Does NOT authorize enabling REASONING_LIVE_NETWORK_ENABLED
Does NOT authorize validating, testing, or otherwise exercising the provisioned credential against
   Anthropic
Does NOT pre-authorize any previously DISCUSSED live-validation envelope. A call count, a total cost
   ceiling, a per-call ceiling, the allowed verbs, the environment, the gate enablement, the
   credential use and the abort conditions must all be named explicitly by a future Product Owner
   decision before the first real external call
Does NOT authorize AT-M4 or any real work execution
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT change SecretProvider's global semantics, add a write path to the SDK, or widen the scoped
   runtime token's policy
Does NOT amend AT-D26, AT-D27, AT-D28 or AT-D29
Does NOT authorize any runtime image rebuild or redeploy -- the already-aligned image is used as-is;
   only `docker compose restart orchestrator` (not --force-recreate) is authorized, because only a
   Vault secret VALUE changes, not the environment
Does NOT claim the runtime is production-ready in any respect
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=true public-exposure=false live-integrations=disabled -->
