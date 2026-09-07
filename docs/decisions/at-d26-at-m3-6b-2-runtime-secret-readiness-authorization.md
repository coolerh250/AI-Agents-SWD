# AT-D26 — AT-M3.6B.2 runtime secret readiness authorization

> **Product Owner decision record. Authorizes ONE bounded infrastructure/configuration slice: giving
> the internal non-production test runtime a persistent Vault and the wiring to read a live
> reasoning credential from it. It authorizes NO real Anthropic call, NO diagnostic external call,
> NO live-gate enablement, NO provisioning of a real API key, NO live validation, NO real work
> execution (AT-M4), NO production action and NO HumanApproval mutation.
> `production_executed_true_count: 0`.**

```text
AT-D26:                      RESOLVED / BINDING
Recorded_on:                 2026-09-07
Recorded_by:                 Product Owner
Canonical_main_at_decision:  446f4cce517a78463371a57986dbdad67f2470e2
Branch:                      at-m3.6b.2-runtime-secret-readiness-1
Depends_on:                  AT-D24 (docs/decisions/at-d24-at-m3-6b-1-live-reasoning-provider-implementation-authorization.md)
                             AT-D25 (docs/decisions/at-d25-at-m3-6b-1-live-reasoning-provider-acceptance-and-merge-authorization.md)

AT-M3.6B.1:                      CLOSED / CANONICAL
AT-M3.6B.2 LIVE VALIDATION:      NOT AUTHORIZED
THIS SLICE:                      AUTHORIZED
REAL ANTHROPIC CALLS:            0
DIAGNOSTIC EXTERNAL CALLS:       0
REASONING_LIVE_NETWORK_ENABLED:  false
AT-M4:                           NOT AUTHORIZED
Production:                      NOT GRANTED
production_executed_true_count:  0
```

## 1. What this record is for

AT-D25 closed AT-M3.6B.1 and said plainly what it did not establish: the runtime is *structurally*
ready for a live provider, and nothing about real connectivity, credentials or billing has been
shown, because zero real calls were made. The AT-M3.6B.2 secret-provisioning preflight then found
three environment facts standing between that structural readiness and a Product Owner being able to
provision a key at all:

1. no Vault was running on the internal test runtime;
2. the compose file ran `vault server -dev`, whose storage is in memory — a key written there is
   lost on every restart and the root token changes each start;
3. no deployment config wired the runtime to Vault, or to the reasoning provider, at all, so a
   correctly provisioned key would not have been read by anything.

This record authorizes fixing exactly those three, and nothing beyond them. It is deliberately a
separate decision from the one that will authorize the first real call: preparing a rail and
travelling it are different risks, and collapsing them is how a "readiness" slice quietly becomes a
live integration.

## 2. Authorized scope

```text
a PERSISTENT non-production Vault replacing `server -dev`
    - file storage on a named Docker volume, surviving container recreation and restart
    - internal-only: no TLS (documented), loopback-published, never publicly exposed
    - no auto-unseal, no HA, no Raft; manual unseal, stated rather than hidden
a LEAST-PRIVILEGE runtime Vault policy
    - read, on exactly one path: secret/data/aiagents/test-runtime
    - no write, patch, delete, destroy, list, sudo; no sys/, auth/ or identity/; no wildcard
RUNTIME WIRING on the orchestrator service
    - SECRET_PROVIDER=vault, VAULT_ADDR (internal), VAULT_KV_MOUNT=secret,
      VAULT_KV_PATH=aiagents/test-runtime
    - REASONING_PROVIDER=anthropic, REASONING_MODEL=claude-sonnet-5
    - REASONING_LIVE_NETWORK_ENABLED=false
a `test-runtime` MODE on the EXISTING canonical runtime-config validator
    - asserts the above explicitly, so SECRET_PROVIDER cannot fall back to env silently
ANTHROPIC_API_KEY declared in infra/runtime/secrets.inventory.yml, metadata only
an OPERATOR BOOTSTRAP RUNBOOK and a value-free verification script
bounded tests over all of it
```

## 3. What is NOT authorized

```text
Provisioning the real Anthropic key   NOT AUTHORIZED by this record. The operator provisions it
                                         manually, after this slice passes Independent Validation
                                         AND AT-M3.6B.2 is separately authorized
Reading an existing Anthropic key     NOT AUTHORIZED
Any real Anthropic call               NOT AUTHORIZED
Any diagnostic external call          NOT AUTHORIZED -- the Step 65F-C guardrail is unchanged:
                                         every external call counts, diagnostic ones included
Enabling the live network gate        NOT AUTHORIZED, not even briefly, not even to verify
Credential validation of any kind     NOT AUTHORIZED
AT-M3.6B.2 Live Validation            NOT AUTHORIZED -- this record prepares for it and does not
                                         perform any part of it
AT-M4 implementation                  NOT AUTHORIZED
Live M3.5 dispatch consumer           NOT AUTHORIZED
Production action                     NOT AUTHORIZED
Production authorization              NOT GRANTED -- unchanged
HumanApproval mutation                NOT AUTHORIZED
A second secret-management authority  NOT AUTHORIZED -- see section 7
```

## 4. The bootstrap boundary, and why it is where it is

Initializing a Vault produces two things that must never enter a repository, a chat transcript, a
log or a test fixture: the **unseal/recovery key shares** and the **initial root token**. An
assistant that ran `vault operator init` would render both into its own conversation, and nothing
afterwards un-renders them.

So the boundary is drawn immediately before initialization. Everything expressible as configuration
is prepared, committed and tested; the three steps that mint secrets — initialize, unseal, create
the runtime token — belong to the operator, in their own terminal, with the material retained
outside this repository and outside any AI conversation. The procedure is
`docs/operations/at-m3-6b-2-vault-runtime-readiness-runbook.md`.

**This checkpoint is the expected shape of a secure bootstrap, not a failure of the slice.** The
alternative — weakening Vault so no bootstrap secret exists — would trade a process step for a
permanent security property, which is the wrong trade.

Vault authority is split accordingly, and the split is enforced by Vault rather than by convention:

| Authority | Held by | Used for | Ever injected into a service? |
| --- | --- | --- | --- |
| unseal key, root token | the operator, offline | initialize, unseal, write policy, mint tokens, provision the key | **never** |
| `aiagents-runtime-read` token | the orchestrator | read one secret | yes, and only this |

## 5. The placeholder is not a credential

The canonical path may carry `ANTHROPIC_API_KEY` with the repository's existing non-secret sentinel
`PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE`, so the field NAME exists and the rail can be verified end to
end. `SecretProvider.get_secret()` has treated that exact string as **absent** since Stage 24, so:

```text
list_available_secrets()          ->  contains ANTHROPIC_API_KEY      (the name is visible)
get_secret("ANTHROPIC_API_KEY")   ->  present=False                   (the credential is not)
```

No realistic-looking `sk-ant-…` value is created. A fake that looks real is a fake that gets treated
as real by the next person who reads it.

And provisioning is not, by itself, an enablement: the adapter checks the network gate **first**, so
even a runtime holding a real key refuses before the credential is resolved.

## 6. Non-production limitations, recorded rather than implied

```text
No TLS on the Vault listener      Internal compose network only, loopback-published. Production
                                     terminates TLS here; this configuration would be wrong for one
Manual unseal after every restart Vault re-seals on restart and stays sealed until an operator
                                     unseals it. Auto-unseal needs a cloud KMS or transit seal that
                                     does not exist in this project, and inventing one is a bigger
                                     change than a readiness slice should make. Meanwhile the
                                     provider reports every secret absent and the adapter fails
                                     closed -- degraded, never silently switched to another source
`file` storage, single node       Losing the volume loses the store. Acceptable for one
                                     non-production credential; it is why bootstrap material is
                                     kept off the volume
Runtime token via env var         Visible to `docker inspect` on the host. It is the only
                                     distribution mechanism this repository has, and inventing a
                                     second one is out of scope
One operator holds the unseal     No custodian separation. Single-operator non-production runtime;
   key and the root token            `-key-shares=1` is chosen for that reality, not defended as
                                     good production practice
Provider caches per process       A key written after startup is not read until the process
                                     restarts. Documented and tested, not fixed -- see section 7
```

None of these is acceptable for production, and none is claimed to be.

## 7. No new authority, and one thing deliberately not built

The slice reuses what exists and adds nothing that could become a second source of truth:

```text
SecretProvider          unchanged. No global provider semantics were altered
llm_budget              untouched
ReasoningService        untouched
validate_runtime_config a MODE was added to the existing canonical validator, not a second
                        validator beside it
secrets.inventory.yml   an ENTRY was added to the existing inventory
```

Not built, on purpose: **no hot-secret-reload subsystem.** `VaultKvSecretProvider` caches the KV
document for the life of the process, so a key written after startup is invisible until a restart.
That is documented, tested and handled by the runbook requiring an explicit
`docker compose restart orchestrator`. A reasoning runtime that could silently change which
credential it bills to, mid-process, is a worse property than one that needs a restart you can point
at in a deployment log.

Also not built: no credential broker, no rotation daemon, no auto-unseal architecture, no provider
registry, no live-validation framework, no secret governance platform.

## 8. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B.2 Live Validation, or any part of it
Does NOT authorize a real external call of any kind, official or diagnostic
Does NOT authorize enabling REASONING_LIVE_NETWORK_ENABLED
Does NOT authorize provisioning, reading, validating or exercising a real Anthropic credential
Does NOT pre-authorize any previously DISCUSSED live-validation envelope. A call count, a total
   cost ceiling, a per-call ceiling, the allowed verbs, the environment, the gate enablement, the
   credential use and the abort conditions must all be named explicitly by a future Product Owner
   decision before the first real external call
Does NOT authorize AT-M4 or any real work execution
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT change SecretProvider's global semantics
Does NOT amend AT-D24 or AT-D25
Does NOT amend or reopen AT-D18
Does NOT dispose of HAZARD_AT_M3_LIVE_DENYLIST
Does NOT repair the Step 66 stage-freeze guards
Does NOT claim the runtime is production-ready in any respect
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
