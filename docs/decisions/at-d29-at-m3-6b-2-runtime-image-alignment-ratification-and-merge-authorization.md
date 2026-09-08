# AT-D29 — AT-M3.6B.2 Runtime Image Alignment safety-surface remediation ratification, product acceptance & canonical merge authorization

> **Product Owner decision record. Ratifies the already-implemented, bounded safety-surface
> remediation on branch `at-m3.6b.2-runtime-image-alignment-1` (fixing `/operations/safety`
> `vault_reachable` truthfulness and correcting `VAULT_TOKEN` classification), accepts the
> AT-M3.6B.2 Runtime Image Alignment stage as product-accepted, and authorizes merging the exact
> independently validated candidate into `main`. Independent Validation 1 reproduced every
> load-bearing technical acceptance item as PASS; its overall FAIL verdict rested solely on a
> missing citable Product Owner authorization record for the remediation, which this record
> supplies. Authorizes no real Anthropic key, no diagnostic or real external call, no live-gate
> enablement, no credential validation, no further runtime rebuild or redeploy, no AT-M3.6B.2 Live
> Validation, no AT-M4, no production action, no HumanApproval mutation.
> `production_executed_true_count: 0`.**

```text
AT-D29:                      RESOLVED / BINDING
Recorded_on:                 2026-09-08
Recorded_by:                 Product Owner
Canonical_main_at_decision:  12eda4f7b4743293e0de3798652ce637f61e5edb
Validated_candidate:         158c8a840a79eb8912420eda63c233c5c4193499
Implementation_end:          158c8a840a79eb8912420eda63c233c5c4193499
Branch:                      at-m3.6b.2-runtime-image-alignment-1
Depends_on:                  AT-D26 (docs/decisions/at-d26-at-m3-6b-2-runtime-secret-readiness-authorization.md)
                             AT-D27 (docs/decisions/at-d27-at-m3-6b-2-runtime-secret-readiness-acceptance-and-merge-authorization.md)
                             AT-D28 (docs/decisions/at-d28-at-m3-6b-2-runtime-image-alignment-authorization.md)
```

`Implementation_end` is the exact byte state that was independently validated. This record and the
bounded PM/progress reconciliation commit it authorizes create a later branch tip;
`Implementation_end` does not move with it. Acceptance attaches to a commit, not to a branch name.

## 1. What this record is for

AT-D28 authorized exactly one bounded deployment action: rebuilding and redeploying the internal
test orchestrator from canonical main, closing the deployment-representativeness gap AT-D27 section
4 recorded. Executing that authorization surfaced a second, load-bearing defect not visible until
current code ran against a real persistent Vault: `_secret_provider_status()` in
`apps/orchestrator/src/operations.py` read a fresh `VaultKvSecretProvider`'s `.status` before
anything had triggered a lookup, so `vault_reachable` read `False` unconditionally regardless of
actual Vault reachability, and `VAULT_TOKEN` was checked as if it were a Vault KV document field
rather than the environment-supplied transport credential it actually is. The implementer correctly
recognized that fixing `apps/orchestrator/src/operations.py` was outside AT-D28's own authorized
scope (image rebuild/redeploy only, with a Dockerfile/build-context defect as the sole named
exception) and reported the stage as FAIL rather than silently patching application logic under a
deployment-only authorization.

Independent Validation 1 (`AT-M3.6B.2-RUNTIME-IMAGE-ALIGNMENT-INDEPENDENT-VALIDATION-1`)
subsequently and independently reproduced every load-bearing technical acceptance item as PASS —
deployed image alignment, reasoning-module presence, byte-for-byte repo/container hash alignment,
the safety-surface root cause and its fix, Vault reachability truthfulness, `VAULT_TOKEN`
classification, Vault readiness, `SecretProvider` end-to-end behavior, the placeholder/real-key
boundary, zero Anthropic calls, and the fail-closed live gate — but returned an overall FAIL
verdict, because the remediation commit (`d7eda04`) modifying `apps/orchestrator/src/operations.py`
had no citable Product Owner authorization of its own; AT-D28 explicitly excludes business-logic
changes outside its narrow Dockerfile/build-context exception, and no `AT-D29` or `AT-D28` addendum
existed at that time. The validator classified this as `RISK_CLASS: P2 / GOVERNANCE / PROCESS GAP`,
not a P0/P1 product-blocking defect, and recommended the Product Owner supply the missing
authorization record rather than requiring a second technical validation round.

This record is that authorization. It ratifies the remediation exactly as implemented and
independently validated, with no code change of any kind, and authorizes canonicalizing the exact
validated candidate. Same shape as AT-D13/AT-D15/AT-D19/AT-D20/AT-D21/AT-D22/AT-D23/AT-D25/AT-D27:
implementation authority and merge authority are separate decisions, and this one names the commit.

## 2. Ratified remediation scope

Ratified exactly as already implemented on the candidate, and no wider:

```text
FIX 1 -- /operations/safety vault_reachable truthfulness
`_secret_provider_status()` now runs the required-secret probe (the loop calling
    `provider.has_secret(name)`, which is what actually exercises the provider) BEFORE reading
    `provider.status`, so `vault_reachable` reflects a real attempt rather than an untouched
    provider's empty cache. Independently reproduced: a fresh `VaultKvSecretProvider` instance's
    `.status["reachable"]` reads `False` before any lookup and `True` immediately after, against
    the actual reachable test Vault, with nothing else changed.

FIX 2 -- VAULT_TOKEN classification
VAULT_TOKEN's entry in `missing_required_secrets` is now checked directly against the process
    environment rather than through `provider.has_secret("VAULT_TOKEN")`. VAULT_TOKEN is the
    transport credential Vault is reached WITH, never a field Vault stores about itself. The other
    three required secrets (POSTGRES_PASSWORD, GITHUB_TOKEN, DISCORD_BOT_TOKEN) are unchanged and
    still checked through the provider.

SCOPE BOUNDARY
Changes limited to `apps/orchestrator/src/operations.py`, the five new focused tests in
    `tests/test_operations_secret_safety.py`, and the progress-ledger entries recording the work.
    No change to `shared/sdk/secrets/provider.py`. No change to `SecretProvider` semantics. No
    change to the Vault runtime-token model, mount, path, or policy. No new secret subsystem.
```

Explicitly recorded, because these are exactly the boundaries Independent Validation 1 verified and
none of them moved:

```text
SecretProvider authority:            UNCHANGED
Vault runtime-token architecture:    UNCHANGED
New secret subsystem:                NONE
```

Capability not named here is not ratified by this record, whether or not code for it happens to
exist.

## 3. Validation disposition

Independent Validation 1 reproduced ALL load-bearing technical acceptance items as PASS:

```text
Deployed image alignment                              PASS (image sha256:ca0aa892... matches
                                                         candidate; repo checkout SHA matches)
Reasoning module presence (import + resolve)           PASS
Repository/container hash alignment (5 files)          PASS (byte-for-byte)
Safety-surface root cause + fix                        PASS (reproduced directly: fresh provider
                                                         reachable=False before lookup,
                                                         True after)
/operations/safety truthfulness (3 fresh requests)     PASS
VAULT_TOKEN classification                             PASS
Vault runtime readiness                                PASS (11/0)
SecretProvider end-to-end                               PASS
Placeholder / real-key boundary                        PASS
Live-gate fail-closed (reproduced live)                PASS
Data / deployment preservation                         PASS
Focused regression tests                               PASS (204 passed / 3 skipped / 0 failed,
                                                         0 candidate regressions)
Security (no secret exposure, .env mode 600, no
  operator/root token used)                            PASS
```

The validator's sole FAIL finding:

```text
RISK_CLASS:              P2
TYPE:                    GOVERNANCE / PROCESS GAP -- missing citable Product Owner authorization
                          record for a business-logic change AT-D28 explicitly excluded
PRODUCT SAFETY IMPACT:   NONE OBSERVED -- the fix is content-correct, safety-improving (makes
                          /operations/safety MORE truthful), and independently proven not to touch
                          secret values, credentials, production, or external calls
P0/P1:                   NONE
```

Product Owner disposition of this finding:

```text
RATIFIED -- see section 2
NO VALIDATION 2 REQUIRED -- the finding was procedural, not technical; every technical item already
    carries independently reproduced PASS evidence, which this record does not re-derive or
    discount
NO CODE REMEDIATION REQUIRED -- the implementation is accepted exactly as validated
```

```text
Validation quota:    1 of 2 consumed
Validation 2:        NOT REQUIRED
```

This record preserves Independent Validation 1's verdict truthfully: it does not restate the
verdict as PASS. It records that the verdict was FAIL, that the FAIL rested on one procedural
finding, and that the Product Owner has now ratified that finding's disposition without altering
any of the technical evidence the validator independently reproduced.

## 4. Accepted technical evidence

Recorded here, not re-run by this decision. Independently reproduced by Independent Validation 1,
not trusted from the implementation report:

```text
DEPLOYED IMAGE
Aligned to candidate 158c8a8: image sha256:ca0aa892cf9956f7ed4377bea5cdab0468815d8117f4f9c07b933139ab999b27
    matches the running container; repo checkout on the test host equals the candidate tip.

REASONING MODULES
AnthropicReasoningProvider, ReasoningService, live_config all import cleanly inside the running
    container. LiveReasoningConfig.resolve() (no network, no credential resolution):
    provider_name=anthropic, model_name=claude-sonnet-5, model_is_authorized=true,
    live_network_enabled=false.

HASH ALIGNMENT
anthropic_provider.py, service.py, live_config.py, shared/sdk/secrets/provider.py, operations.py --
    5/5 byte-identical (SHA-256) between the repository and the running container.

SAFETY SURFACE (fresh /operations/safety, 3 consecutive independent requests)
vault_configured=true, vault_reachable=true, secret_provider=vault, missing_required_secrets=
    [POSTGRES_PASSWORD, GITHUB_TOKEN, DISCORD_BOT_TOKEN] (VAULT_TOKEN correctly absent),
    reasoning_provider=anthropic, reasoning_model=claude-sonnet-5, reasoning_provider_mode=live,
    reasoning_model_allowlisted=true, reasoning_live_enabled=false,
    production_executed_true_count=0. No secret value in any response.

VAULT_TOKEN CLASSIFICATION
Present, non-empty, in the orchestrator's own process environment (never displayed); sourced from
    `infra/docker-compose/.env`, mode 600, containing exactly one key (VAULT_TOKEN). Not treated as
    a Vault KV document field. Not falsely listed in missing_required_secrets when present.

VAULT READINESS
scripts/verify_vault_runtime_readiness.sh independently re-run (token read from the orchestrator
    container's own environment, never printed): VAULT_RUNTIME_READINESS: PASS, 11 passed / 0
    failed. initialized=true, sealed=false, storage=file, KV v2 mount=secret, canonical path
    secret/data/aiagents/test-runtime. Scoped runtime token: canonical raw read PASS; write,
    delete, unrelated path, metadata path, sys/policy all DENIED. Allow-before-deny ordering
    independently confirmed.

SECRETPROVIDER, THROUGH THE ACTUAL DEPLOYED CODE PATH
provider_class=VaultKvSecretProvider, mount=secret, path=aiagents/test-runtime.
    list_available_secrets()=[ANTHROPIC_API_KEY]. get_secret(ANTHROPIC_API_KEY).present=false.
    has_secret(ANTHROPIC_API_KEY)=false. No secret value returned by any call.

PLACEHOLDER / REAL-KEY BOUNDARY
No ANTHROPIC_API_KEY in the container's process environment. No /dev/shm handoff file. No
    `sk-ant-` literal anywhere in the repository (only regex patterns inside secret-scan
    verifiers). infra/docker-compose/.env holds exactly VAULT_TOKEN, mode 600.

LIVE-GATE FAIL-CLOSED
Reproduced live inside the running container: AnthropicReasoningProvider.preflight() raises
    LiveProviderError(failure_category=provider_disabled) at the network-gate check, before budget
    evaluation, before credential resolution, before any network stack is touched.

DATA / DEPLOYMENT PRESERVATION
Vault and Postgres containers' Created timestamps predate the orchestrator redeploy by weeks;
    Vault initialized=true / sealed=false / storage=file unchanged; Postgres audit_logs (129 rows)
    and workflow_states (10 rows) non-empty and unchanged -- the orchestrator-only, --no-deps
    redeploy did not reset Vault or Postgres state.

REGRESSION TESTS
tests/test_operations_secret_safety.py, test_at_m3_6b_1_safety_surface.py,
    test_at_m3_6b_1_anthropic_adapter.py, test_at_m3_6b_1_service_contract.py,
    test_at_m3_6b_2_runtime_secret_readiness.py, test_at_m3_6b_2_operator_handoff.py -- run
    independently against a throwaway database and disposable worktree at candidate 158c8a8, real
    PostgreSQL: 204 passed / 3 skipped / 0 failed. The 3 skips are environment-dependent (no
    bootstrapped Vault / no deployment .env in the isolated worktree), not candidate regressions.

ANTHROPIC CALLS
0 real, 0 diagnostic, throughout implementation and validation.

P0/P1 CANDIDATE DEFECTS
None found.
```

## 5. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the exact validated candidate
                               158c8a8 into main
Documentation-only authority:  this record and the bounded PM/progress reconciliation commit it
                               authorizes
Post-merge verification:       bounded, value-free repository-truth checks only -- confirming the
                               ratified remediation and the AT-M3.6B.1/AT-M3.6B.2 assets are present
                               in the repository at the merged tip. No runtime rebuild, redeploy, or
                               re-query of the live deployed system is authorized or implied by this
                               verification.
```

## 6. What is NOT authorized

```text
Real ANTHROPIC_API_KEY provisioning   NOT AUTHORIZED. Reserved for a future, separate Product Owner
                                         decision (AT-M3.6B.2 Real Anthropic Secret Provisioning
                                         Authorization)
Reading an existing Anthropic key     NOT AUTHORIZED
AT-M3.6B.2 Live Validation            NOT AUTHORIZED -- its own future, separate authorization must
                                         name provider, model, call count, cost ceilings, allowed
                                         verbs, environment, gate enablement, credential use and
                                         abort conditions
Any real Anthropic call               NOT AUTHORIZED
Any diagnostic external call          NOT AUTHORIZED
Enabling the live network gate        NOT AUTHORIZED, not even briefly, not even to verify
Any further runtime image rebuild     NOT AUTHORIZED by this record -- the image already aligned and
  or redeploy                           validated is accepted as-is; no new deployment action
AT-M4 implementation                  NOT AUTHORIZED
Production action                     NOT AUTHORIZED
Production authorization              NOT GRANTED -- unchanged
HumanApproval mutation                NOT AUTHORIZED
Any change to shared/, apps/,         NOT AUTHORIZED by this record -- this is a documentation-only
  agents/, migrations/, infra/,         canonicalization; the accepted implementation is exactly
  scripts/, or tests/                   candidate 158c8a8 and this record adds no code
A second secret-management authority  NOT AUTHORIZED
```

## 7. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B.2 Live Validation, or any part of it
Does NOT authorize a real external call of any kind, official or diagnostic
Does NOT authorize enabling REASONING_LIVE_NETWORK_ENABLED
Does NOT authorize provisioning, reading, validating or exercising a real Anthropic credential
Does NOT authorize any further rebuild, redeploy, or mutation of the running orchestrator image or
   any other deployed container
Does NOT claim the currently deployed test orchestrator is ready for a live provider call --
   real-key provisioning and Live Validation remain separately gated, unmade Product Owner decisions
Does NOT pre-authorize any previously DISCUSSED live-validation envelope
Does NOT authorize AT-M4 or any real work execution
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT change SecretProvider's global semantics
Does NOT amend AT-D26, AT-D27 or AT-D28
Does NOT reclassify Independent Validation 1's technical findings -- they stand exactly as
   independently reproduced in section 4
Does NOT retroactively expand AT-D28's own scope -- it ratifies the remediation as a NEW,
   independent authorization, not as something AT-D28 is reread to have already covered
Does NOT add a verifier, registry, exemption mechanism, or new governance layer of any kind
Does NOT decide what follows this canonicalization -- AT-M3.6B.2 Real Anthropic Secret Provisioning
   Authorization, AT-M3.6B.2 Live Validation and AT-M4 remain separate, unmade Product Owner
   decisions
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
