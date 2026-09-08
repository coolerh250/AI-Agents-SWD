# AT-D27 — AT-M3.6B.2 Runtime Secret Readiness product acceptance & canonical merge authorization

> **Product Owner decision record. Accepts AT-M3.6B.2 Runtime Secret Readiness (the persistent
> non-production Vault, the least-privilege runtime policy, the orchestrator secret wiring, the
> `test-runtime` validator mode, the secrets-inventory entry, the operator bootstrap runbook and the
> hardened value-free readiness verifier) and authorizes merging the exact independently validated
> candidate into `main`. Acceptance is `PASS_WITH_PREREQUISITE`: the secret substrate itself —
> Vault, its policy, its wiring, and the canonical `SecretProvider` reading through it — is
> independently proven ready. The currently deployed internal test orchestrator image is NOT
> accepted as ready for a live provider, because it predates AT-M3.6B.1 and does not contain the
> canonical reasoning runtime; that gap is recorded as a binding prerequisite in section 4, not
> waived and not silently absorbed into this acceptance. Authorizes no real external LLM call, no
> diagnostic external call, no live-gate enablement, no real Anthropic key provisioning, no runtime
> image rebuild or redeploy, no AT-M3.6B.2 Live Validation, no real work execution (AT-M4), no
> production action, no HumanApproval mutation. `production_executed_true_count: 0`.**

```text
AT-D27:                      RESOLVED / BINDING
Recorded_on:                 2026-09-08
Recorded_by:                 Product Owner
Canonical_main_at_decision:  446f4cce517a78463371a57986dbdad67f2470e2
Validated_candidate:         993e046c3eef6fe380587795a01ae3cb6f8e4cad
Implementation_end:          993e046c3eef6fe380587795a01ae3cb6f8e4cad
Branch:                      at-m3.6b.2-runtime-secret-readiness-1
Depends_on:                  AT-D24 (docs/decisions/at-d24-at-m3-6b-1-live-reasoning-provider-implementation-authorization.md)
                             AT-D25 (docs/decisions/at-d25-at-m3-6b-1-live-reasoning-provider-acceptance-and-merge-authorization.md)
                             AT-D26 (docs/decisions/at-d26-at-m3-6b-2-runtime-secret-readiness-authorization.md)
```

`Implementation_end` is the exact byte state that was independently validated. This record and the
bounded PM/progress reconciliation commit it authorizes create a later branch tip; `Implementation_end`
does not move with it. Acceptance attaches to a commit, not to a branch name.

## 1. What this record is for

AT-D26 authorized exactly one bounded infrastructure/configuration slice: giving the internal
non-production test runtime a persistent Vault and the wiring to read a live reasoning credential
from it. This record is the second and separate decision: the Product Owner accepts the resulting
capability as independently validated, and approves canonicalizing the exact validated candidate.
Same shape as AT-D13/AT-D15/AT-D19/AT-D20/AT-D21/AT-D22/AT-D23/AT-D25: implementation authority and
merge authority are separate decisions, and the second one names the commit.

**What this acceptance is, and what it is not.** AT-M3.6B.2 Runtime Secret Readiness proves the
secret substrate is ready: a persistent, non-dev Vault; a least-privilege runtime policy proven by
live ACL enforcement, not by trusting committed HCL; the canonical `SecretProvider` resolving
`VaultKvSecretProvider` and reading the placeholder through the actual deployed code path; and a
hardened, value-free readiness verifier that fails closed on a missing token and orders canonical
read before any denial check. It does **not** prove the runtime is ready to carry a live reasoning
call: the deployed orchestrator image independently confirmed to be running during Independent
Validation 1 predates AT-M3.6B.1 and contains neither `shared.sdk.agent_reasoning` nor
`shared.sdk.reasoning`, and its `/operations/safety` surface reports stale, false readings
(`vault_reachable: false`, `llm_provider: mock`) precisely because it cannot execute the current
wiring. Reading this record as "the runtime can carry live reasoning" would be exactly the
misreading AT-D25 section 1 warned against for AT-M3.6B.1, one level further down the stack.

## 2. Accepted product capability

Accepted exactly as independently validated, and no wider:

```text
VAULT
persistent, non-dev Vault: `server` (not `server -dev`) against `file` storage on a named Docker
    volume, surviving container recreation and restart -- independently confirmed: initialized=true,
    sealed=false, storage=file, and Vault's own uptime outlived a later orchestrator recreation
KV v2 at mount `secret`, canonical path `secret/data/aiagents/test-runtime` -- confirmed
    behaviorally by the nested data/data response envelope unique to v2, the runtime token having
    no sys/mounts access by design
field `ANTHROPIC_API_KEY` carries the repository's existing non-secret sentinel
    `PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE`; compared inside a script, never rendered to any session

POLICY, PROVEN BEHAVIORALLY
`aiagents-runtime-read`: canonical raw read (secret/data/aiagents/test-runtime) ALLOWED; write,
    delete, unrelated path, metadata path, sys/policy, sys/policies/acl, token create, list and
    sys/mounts all independently reproduced DENIED (403) against the actual runtime token
runtime token confirmed non-root: its own self-lookup (auth/token/lookup-self) is refused, which is
    only possible for a non-root token
allow-before-deny ordering independently reproduced, not merely asserted by the readiness script

RUNTIME WIRING
orchestrator env, read directly from the running container: SECRET_PROVIDER=vault,
    VAULT_ADDR=http://vault:8200, VAULT_KV_MOUNT=secret, VAULT_KV_PATH=aiagents/test-runtime,
    REASONING_PROVIDER=anthropic, REASONING_MODEL=claude-sonnet-5,
    REASONING_LIVE_NETWORK_ENABLED=false, VAULT_TOKEN present=yes, ANTHROPIC_API_KEY in
    environment=no
`infra/docker-compose/.env`: mode 600, untracked, gitignored, holding exactly one key
    (VAULT_TOKEN) -- no Anthropic material, no root token, no unseal key

SECRETPROVIDER, THROUGH THE ACTUAL DEPLOYED CODE PATH
`provider_from_env()` inside the running orchestrator container resolves `VaultKvSecretProvider` at
    mount `secret`, path `aiagents/test-runtime`; `list_available_secrets() == ["ANTHROPIC_API_KEY"]`;
    `get_secret(...).present=False`; `has_secret(...)=False`
the deployed `shared/sdk/secrets/provider.py` is byte-identical (SHA-256 match) to the repository's
    working-tree copy -- the proof ran through canonical code, not a stale copy of it

READINESS VERIFIER
`scripts/verify_vault_runtime_readiness.sh`: a missing/placeholder `VAULT_TOKEN` is an independently
    reproduced hard FAIL with zero denial checks run (`TOKEN_MISSING_OR_DENIED`); with the correct
    token, canonical read is independently confirmed to log PASS before any denial check;
    independently reproduced final result `VAULT_RUNTIME_READINESS: PASS`, 11 passed / 0 failed

OPERATOR BOOTSTRAP AND AUTHORITY SPLIT
initialize / unseal / mint-token remain operator-only, never performed by an assistant; the
    completed procedure used only a path to an operator-supplied token file, never a pasted value
`docs/operations/at-m3-6b-2-vault-runtime-readiness-runbook.md` correctly distinguishes an
    environment change (VAULT_TOKEN -- requires `--force-recreate`) from a secret-value-only change
    (a process/container restart suffices, because `VaultKvSecretProvider` caches per process)

BOUNDARIES HELD THROUGHOUT
zero real Anthropic calls, zero diagnostic external calls, `REASONING_LIVE_NETWORK_ENABLED=false`
    throughout, no real Anthropic key in Vault, the repository, `.env`, or any `/dev/shm` handoff
    file, `production_executed_true_count=0` queried live from the deployed runtime
```

This list is the acceptance boundary. Capability not named here is not accepted by this record,
whether or not code for it happens to exist.

## 3. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the exact validated candidate
                               993e046 into main
Documentation-only authority:  this record and the bounded PM/progress reconciliation commit it
                               authorizes
Post-merge verification:       bounded, value-free repository-truth checks only -- confirming the
                               readiness assets and the AT-M3.6B.1 reasoning runtime are present in
                               the repository. No claim about the currently deployed image is made
                               or implied by this verification.
```

## 4. Binding prerequisite — REQUIRED_BEFORE_REAL_SECRET_PROVISIONING_OR_LIVE_VALIDATION

Independent Validation 1 found, and this decision records as load-bearing, that the internal
non-production test orchestrator's currently deployed image (built 2026-07-14, roughly two months
before this work) predates AT-M3.6B.1: `import shared.sdk.agent_reasoning` and
`import shared.sdk.reasoning` both fail inside the running container with `ModuleNotFoundError`, and
the container's own `/operations/safety` reports `vault_reachable: false` and `llm_provider: mock` —
both demonstrably false given the Vault reads and `REASONING_PROVIDER=anthropic` wiring independently
proven in section 2. This is **not** a defect introduced by the AT-M3.6B.2 candidate: AT-D26 section
2 authorized Vault persistence, the policy, the wiring configuration, the validator mode, the secrets
inventory entry, the runbook and bounded tests — deploying a rebuilt orchestrator image was never
part of that authorized scope, and this record does not retroactively expand it.

```text
REQUIRED_BEFORE_REAL_SECRET_PROVISIONING_OR_LIVE_VALIDATION:

  The internal non-production test orchestrator image MUST be rebuilt and redeployed from canonical
  main before either (a) a real ANTHROPIC_API_KEY is provisioned into Vault, or (b) any AT-M3.6B.2
  Live Validation is authorized or attempted.

  The rebuilt/redeployed image must contain, at minimum:
    - shared/sdk/agent_reasoning (AnthropicReasoningProvider and the rest of the AT-M3.6B.1 adapter)
    - the ReasoningService / live_config path AT-M3.6B.1 canonicalized

  Once redeployed, /operations/safety must return TRUTHFUL evidence for:
    - Vault reachability and configuration (matching what this record's section 2 already proves at
      the SecretProvider layer)
    - provider = anthropic, model = claude-sonnet-5
    - live gate = false, until AT-M3.6B.2 Live Validation is separately authorized

CLASSIFICATION: PREREQUISITE, NOT A DEFECT IN THE ACCEPTED READINESS SLICE. It gates the NEXT stage
  (image alignment, then real-key provisioning, then live validation), not this one. This
  acceptance is not conditioned on the prerequisite being satisfied; it is conditioned on the
  prerequisite being RECORDED and BINDING before anything past it is authorized.
```

This decision does not implement the prerequisite. Rebuilding or redeploying the orchestrator image
is explicitly out of scope for this canonicalization and is reserved for a separate, later bounded
stage (`AT-M3.6B.2 Runtime Image Alignment`), which this record does not authorize.

## 5. What is NOT authorized

```text
Real ANTHROPIC_API_KEY provisioning   NOT AUTHORIZED. The operator provisions it manually, only
                                         after the section 4 prerequisite is satisfied AND a future
                                         Product Owner decision separately authorizes it
Reading an existing Anthropic key     NOT AUTHORIZED
AT-M3.6B.2 Live Validation            NOT AUTHORIZED -- blocked on the section 4 prerequisite and on
                                         its own future, separate authorization naming provider,
                                         model, call count, cost ceilings, allowed verbs,
                                         environment, gate enablement, credential use and abort
                                         conditions
Any real Anthropic call               NOT AUTHORIZED
Any diagnostic external call          NOT AUTHORIZED -- the Step 65F-C guardrail is unchanged
Enabling the live network gate        NOT AUTHORIZED, not even briefly, not even to verify
Runtime image rebuild or redeploy     NOT AUTHORIZED by this record -- reserved for
                                         AT-M3.6B.2 Runtime Image Alignment, a separate bounded stage
AT-M4 implementation                  NOT AUTHORIZED
Live M3.5 dispatch consumer           NOT AUTHORIZED
Production action                     NOT AUTHORIZED
Production authorization              NOT GRANTED -- unchanged
HumanApproval mutation                NOT AUTHORIZED
Any change to shared/, apps/,         NOT AUTHORIZED by this record -- this is a documentation-only
  agents/, migrations/, infra/,         canonicalization; the accepted implementation is exactly
  scripts/, or tests/                   candidate 993e046 and this record adds no code
A second secret-management authority  NOT AUTHORIZED
```

## 6. Validation evidence — recorded here, not re-run by this decision

```text
AT-M3.6B.2-RUNTIME-SECRET-READINESS-1 (feat, 69ec856): persistent Vault + runtime secret wiring.
AT-M3.6B.2-RUNTIME-SECRET-READINESS-COMPLETION-1 (2d6bfbc -> 993e046): the readiness proof hardened
  to fail when it proves nothing (a missing token no longer counts refusals as passes), operator
  authority taken as a file path rather than a value, and the executed operator procedure recorded
  with its value-free result.

AT-M3.6B.2-RUNTIME-SECRET-READINESS-INDEPENDENT-VALIDATION-1: PASS_WITH_PREREQUISITE.

  Independently reproduced, not trusted from the implementation report: Vault init/seal/storage
  state; KV v2 behaviorally; the runtime policy's exact allow/deny shape via live API calls against
  the actual scoped token; the canonical SecretProvider through the actual running container,
  including a SHA-256 match against the repository's own file; the hardened readiness verifier's
  missing-token FAIL and its allow-before-deny PASS, both re-run rather than re-read; a focused test
  run (109 passed / 2 skipped, 0 failed) on the two candidate test files; and a comparison run of a
  wider focused set against a fresh worktree at canonical base 446f4cc showing the 7 observed
  failures are byte-for-byte identical on both sides -- zero candidate regressions.

  The one load-bearing finding was deployment representativeness: the currently deployed
  orchestrator image predates AT-M3.6B.1 and cannot execute the reasoning adapter path, confirmed
  directly (ModuleNotFoundError on shared.sdk.agent_reasoning and shared.sdk.reasoning inside the
  running container) rather than taken on the implementation report's word. Because AT-D26's
  authorized scope was always the secret substrate only, and because source/progress.md already
  disclosed the gap rather than concealing it, Independent Validation 1 classified this as a
  prerequisite (section 4 above) rather than a defect in the slice, and returned
  PASS_WITH_PREREQUISITE rather than FAIL.

  No Validation 2 was required. Validation quota: 1 of 2 consumed.
```

**Independent Validation 1's finding on deployment representativeness is recorded here exactly as
returned, not softened.** The secret substrate is accepted as ready; the runtime as a whole is not
accepted as ready to carry a live call, and section 4 is the record of why not and what closes the
gap.

## 7. Retained non-blocking backlog

Recorded here so it is not rediscovered as if new. None blocks this acceptance or this merge, and
none is authorized for remediation by this record.

```text
1  Historical stage-freeze / meta test failures (test_step66c4_be3_ra2m2_canonical_merge.py,
   test_step66c4_be3_ra2m_canonicalization.py) -- independently reproduced as identical on the
   candidate and on canonical base 446f4cc; any branch touching apps/, shared/, migrations/, or
   infra/ trips them by construction.
   Disposition: P3 / HISTORICAL_ONLY / NON_BLOCKING, carried from AT-D25 section 7 and earlier

2  tests/test_local_secret_scan_baseline.py -- one critical finding in
   scripts/verify_step66c4_be3_ra1d_missing_config_json.py, already recorded as active registered
   debt in AI_AGENTS_PM_STATE.md section 7 before this branch existed, and independently reproduced
   as identical on canonical base 446f4cc.
   Disposition: PRE-EXISTING REGISTERED DEBT / NON_BLOCKING, unchanged by this record

3  HAZARD_AT_M3_LIVE_DENYLIST -- open since the AT-M3.1 canonical merge, tracked in
   AI_AGENTS_PM_STATE section 8 as a separate Product Owner item. Not touched, not disposed of, by
   this record.
   Disposition: SEPARATELY TRACKED PO ITEM / NON_BLOCKING

4  /operations/safety on the currently deployed (pre-M3.6B.1) orchestrator image reports stale,
   false fields (vault_reachable=false, llm_provider=mock). This is the same fact as section 4's
   prerequisite, viewed from the safety-surface side, and is closed by the same remediation
   (AT-M3.6B.2 Runtime Image Alignment) rather than separately.
   Disposition: FOLDS INTO SECTION 4 / NON_BLOCKING
```

## 8. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B.2 Live Validation, or any part of it
Does NOT authorize a real external call of any kind, official or diagnostic
Does NOT authorize enabling REASONING_LIVE_NETWORK_ENABLED
Does NOT authorize provisioning, reading, validating or exercising a real Anthropic credential
Does NOT authorize rebuilding, redeploying, or otherwise mutating the running orchestrator image or
   any other deployed container -- AT-M3.6B.2 Runtime Image Alignment is a separate, later, bounded
   stage this record does not authorize
Does NOT claim the currently deployed test orchestrator is ready for a live provider call -- section
   4 records precisely the opposite
Does NOT pre-authorize any previously DISCUSSED live-validation envelope. A call count, a total cost
   ceiling, a per-call ceiling, the allowed verbs, the environment, the gate enablement, the
   credential use and the abort conditions must all be named explicitly by a future Product Owner
   decision before the first real external call
Does NOT authorize AT-M4 or any real work execution
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT change SecretProvider's global semantics
Does NOT amend AT-D24, AT-D25 or AT-D26
Does NOT amend or reopen AT-D18
Does NOT dispose of HAZARD_AT_M3_LIVE_DENYLIST
Does NOT repair the Step 66 stage-freeze guards
Does NOT add a verifier, registry, exemption mechanism, or new governance layer of any kind
Does NOT decide what follows Runtime Image Alignment -- AT-M3.6B.2 Live Validation and AT-M4 remain
   separate, unmade Product Owner decisions
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
