# AT-D31 — AT-M3.6B.2 real Anthropic secret provisioning acceptance and merge authorization

> **Product Owner decision record. Accepts the AT-M3.6B.2 real Anthropic secret provisioning slice
> authorized by AT-D30 and authorizes its fast-forward merge to `main`. It accepts that a real
> non-production credential now exists in the canonical Vault rail and is readable by the canonical
> `SecretProvider`. It authorizes NO use of that credential: no live-gate enablement, no Messages
> API call, no credential-validity probe, no model-list call, no health probe, no pricing request,
> no diagnostic external call of any kind. AT-M3.6B.2 Live Validation remains NOT AUTHORIZED, AT-M4
> remains NOT AUTHORIZED, production remains NOT GRANTED.
> `production_executed_true_count: 0`.**

```text
AT-D31:                      RESOLVED / BINDING
Recorded_on:                 2026-09-08
Recorded_by:                 Product Owner
Canonical_main_before_merge: 04f4bc65931d1cbe3b9de6a7df62e5dbe64cac75
Branch:                      at-m3.6b.2-real-anthropic-secret-provisioning-1
Implementation_end:          62bf1e69d36f810e5444816b4d87a1ea5a0c711f
Depends_on:                  AT-D26 (docs/decisions/at-d26-at-m3-6b-2-runtime-secret-readiness-authorization.md)
                             AT-D27 (docs/decisions/at-d27-at-m3-6b-2-runtime-secret-readiness-acceptance-and-merge-authorization.md)
                             AT-D28 (docs/decisions/at-d28-at-m3-6b-2-runtime-image-alignment-authorization.md)
                             AT-D29 (docs/decisions/at-d29-at-m3-6b-2-runtime-image-alignment-ratification-and-merge-authorization.md)
                             AT-D30 (docs/decisions/at-d30-at-m3-6b-2-real-anthropic-secret-provisioning-authorization.md)

AT-M3.6B.2 RUNTIME SECRET READINESS:        CLOSED / CANONICAL
AT-M3.6B.2 RUNTIME IMAGE ALIGNMENT:         CLOSED / CANONICAL
AT-M3.6B.2 REAL SECRET PROVISIONING:        PO_ACCEPTED / READY_TO_MERGE
AT-M3.6B.2 LIVE VALIDATION:                 NOT AUTHORIZED
Validation quota:                           2 / 2 CONSUMED
Validation 3:                               NOT PERMITTED
REAL ANTHROPIC CALLS:                       0
DIAGNOSTIC ANTHROPIC CALLS:                 0
REASONING_LIVE_NETWORK_ENABLED:             false
AT-M4:                                      NOT AUTHORIZED
Production:                                 NOT GRANTED
production_executed_true_count:             0
```

## 1. What this record accepts

AT-D30 authorized exactly one action: writing the Product Owner's real non-production Anthropic API
key into the already-canonical Vault rail at mount `secret`, path `aiagents/test-runtime`, field
`ANTHROPIC_API_KEY`, by `vault kv patch`, without the credential ever being rendered as a value.
That action has been performed, independently validated, and accepted.

This record accepts the slice and authorizes its merge. It is deliberately a separate decision from
the one that will authorize the first real call, for the same reason AT-D26 §1 and AT-D30 §1 each
drew that line one layer earlier: **preparing a credential and spending it are different risks**,
and a populated field is not permission to use it.

## 2. Accepted implementation candidate

```text
implementation_end   62bf1e69d36f810e5444816b4d87a1ea5a0c711f
branch               at-m3.6b.2-real-anthropic-secret-provisioning-1
commits              19194ea  feat -- bounded real-Anthropic-key Vault provisioning helper (AT-D30)
                     62bf1e6  fix  -- declared-fixture Anthropic-key literal in the CLI-rejection test
diff vs main         3 files, +822, -0   (1 decision record, 1 script, 1 test module)
                     docs/decisions/at-d30-...-real-anthropic-secret-provisioning-authorization.md
                     scripts/provision_anthropic_key_to_vault.sh
                     tests/test_at_m3_6b_2_real_anthropic_secret_provisioning.py
```

No file under `apps/`, `shared/`, `agents/`, `migrations/`, `infra/` or the existing test corpus was
touched. The provisioned credential itself is runtime state in Vault and appears nowhere in this
repository, by construction.

## 3. Validation history, recorded as it happened

```text
Independent Validation 1        FAIL
    One bounded finding: a synthetic test-fixture literal in the CLI-rejection test tripped the
    repository's own secret-hygiene scanner. The literal was never a credential -- it was an
    invalid-shape value passed to prove that `--api-key VALUE` is rejected as an unsupported flag --
    but it did not contain one of the scanner's recognized fixture markers as a contiguous
    substring, so the scanner could not tell that from the outside. That is the scanner behaving
    correctly: a value that cannot be distinguished from a credential is treated as one.

Remediation                     single declared-fake fixture correction only
    One test line. The old literal spelled its disclaimer as "not-a-real", which is not one of the
    scanner's recognized markers; the replacement carries `NOT-REAL` contiguously and declares
    itself. The offending literal is deliberately NOT reproduced in this record -- writing a
    scanner-tripping value into a governance document to describe a scanner-tripping value is the
    same mistake one layer up. No production code, no script, no policy, no configuration, no other
    test. The assertion's intent is unchanged: the flag is rejected regardless of the value passed.

Independent Validation 2 / 2    FINAL PASS

Validation quota                2 of 2 CONSUMED
Validation 3                    NOT PERMITTED
```

**Validation 1 is recorded as FAIL and is not rewritten.** It was a real finding against a real
control, and the fact that it was cheap to fix does not make it retroactively a pass. The value of
the scanner is precisely that it cannot be argued with about intent.

## 4. Accepted technical state

```text
Vault                    persistent, initialized, unsealed, KV v2
Canonical secret         mount  secret
                         path   aiagents/test-runtime
                         field  ANTHROPIC_API_KEY
SecretProvider           VaultKvSecretProvider
                         present   = true
                         has_secret = true
Secret value             NEVER RECORDED -- not read, printed, hashed, measured, compared or
                            rendered at any point, in any artifact, or in any conversation
Runtime environment      ANTHROPIC_API_KEY absent -- the credential is reachable only through the
                            Vault rail, never as a process environment variable
Vault runtime token      least privilege, unchanged -- read, on one path; the write required
                            operator authority, which was supplied by opaque file handoff and
                            never entered an assistant conversation
Handoff files            temporary API-key file      removed
                         temporary operator-token file  removed
Reasoning provider       anthropic
Reasoning model          claude-sonnet-5
reasoning_live_enabled   false
Real Anthropic calls           0
Diagnostic Anthropic calls     0
production_executed_true_count 0
```

The provisioning helper enforces the handling contract of AT-D30 §4 in code rather than by
convention: file-path-only interfaces for both credentials, no value in argv, stdin transport into
Vault, `kv patch` and never `put`, refusal to run at all while the live gate is open, and
`docker compose restart` rather than `--force-recreate` because only a secret value changed and not
the runtime environment. Twenty-eight tests hold it to those properties.

## 5. What the populated field does NOT mean

```text
Does NOT mean the credential is valid          -- it has never been used against Anthropic, and no
                                                  probe, health check or model-list call was made
Does NOT mean live reasoning works             -- REASONING_LIVE_NETWORK_ENABLED is false, and the
                                                  adapter checks the gate BEFORE resolving the
                                                  credential, so the runtime still refuses
Does NOT mean AT-M3.6B.2 Live Validation is authorized, implied, or scheduled
Does NOT establish anything about connectivity, latency, model behaviour, billing or cost
```

Reading `present=true` as "the runtime can now make a live call" is the same misreading this
register has warned against at each layer of AT-M3.6B, one layer further down. The credential is
loaded; the safety is that nothing is permitted to pull the trigger.

## 6. Merge authorization

```text
Method              git merge --ff-only
Reconciliation      docs/governance only -- this record, AI_AGENTS_PM_STATE.md, source/progress.md
Guarded trees       apps/ shared/ agents/ migrations/ infra/ scripts/ tests/ MUST be byte-identical
                       between implementation_end and the reconciliation tip
Prohibited          squash, rebase, cherry-pick rewrite, merge commit, force push
```

`AT_M3_6B_2_PROVISIONING_IMPLEMENTATION_END` names `62bf1e6`, the exact independently validated
commit, and does not follow the branch tip. The reconciliation commit that lands on top is
documentation and never carried validation coverage; moving the field to name it would silently
claim coverage the docs commit never had.

## 7. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B.2 Live Validation, or any part of it
Does NOT authorize a real external call of any kind, official or diagnostic
Does NOT authorize enabling REASONING_LIVE_NETWORK_ENABLED, not even briefly, not even to verify
Does NOT authorize validating, probing, rotating or re-provisioning the credential
Does NOT authorize reading the credential's value, prefix, length or hash
Does NOT authorize any runtime action -- no build, redeploy, restart, Vault mutation, or rerun of
   the provisioning helper; the independently validated runtime evidence is carried forward as-is
Does NOT pre-authorize any previously DISCUSSED live-validation envelope. A call count, a total
   cost ceiling, a per-call ceiling, the allowed verbs, the environment, the gate enablement, the
   credential use and the abort conditions must all be named explicitly by a future Product Owner
   decision before the first real external call
Does NOT authorize a Validation 3 -- the quota is 2 of 2 consumed
Does NOT authorize AT-M4 or any real work execution
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT amend AT-D26, AT-D27, AT-D28, AT-D29 or AT-D30
Does NOT reopen the pre-existing secret-scan baseline debt, which remains PRE_EXISTING /
   NON_BLOCKING with no candidate impact
Does NOT claim the runtime is production-ready in any respect
```

## 8. Next decision

`AT-M3.6B.2 Live Validation` — **NOT AUTHORIZED**. It requires its own Product Owner decision
naming the provider, the model, the call count, the total and per-call cost ceilings, the allowed
verbs, the environment, the gate enablement, the credential use and the abort conditions. Nothing
in this record, and nothing about the credential now sitting in Vault, supplies any of them.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=true public-exposure=false live-integrations=disabled -->
