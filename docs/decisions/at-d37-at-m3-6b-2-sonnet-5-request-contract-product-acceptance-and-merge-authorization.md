# AT-D37 — AT-M3.6B.2 Sonnet 5 request contract product acceptance and merge authorization

> **Product Owner decision record. Accepts the AT-M3.6B.2 Sonnet 5 request-contract remediation
> authorized by AT-D36, on the strength of a PASS Independent Implementation Validation, and
> authorizes its fast-forward merge to `main`. It accepts that the canonical Anthropic Messages
> request built by `AnthropicReasoningProvider` no longer carries `temperature`, and that
> `GENERATION_TEMPERATURE` / `GenerationProfile.temperature` are retired. It authorizes NO Anthropic
> call, NO live-gate enablement, NO budget-policy change, NO credential access, NO failure-taxonomy
> change, NO migration, and NO runtime deployment. AT-M3.6B.2 Live Validation remains NOT YET
> successful and stays blocked on a runtime image redeploy this record does not perform.
> `production_executed_true_count: 0`.**

```text
AT-D37:                      RESOLVED / BINDING
Recorded_on:                 2026-09-10
Recorded_by:                 Product Owner
Canonical_main_before_merge: fc9608d443ce31617abcc7c53ed31a30ebf1ce4a
Branch:                      at-m3.6b.2-sonnet5-request-contract-remediation-1
Implementation_end:          d1deae9aa0f0b47ba2a68dbaec9c1aab4dd04451
Depends_on:                  AT-D32 (docs/decisions/at-d32-at-m3-6b-2-live-validation-authorization.md)
                             AT-D34 (docs/decisions/at-d34-at-m3-6b-2-test-runtime-database-migration-alignment-authorization.md)
                             AT-D35 (docs/decisions/at-d35-at-m3-6b-2-live-validation-budget-policy-reactivation-authorization.md)
                             AT-D36 (docs/decisions/at-d36-at-m3-6b-2-anthropic-sonnet-5-request-contract-remediation-authorization.md)

AT-M3.6B.2 SONNET 5 REQUEST CONTRACT REMEDIATION:  PO_ACCEPTED / MERGED / CANONICAL
AT-M3.6B.2 LIVE VALIDATION:                        NOT YET SUCCESSFUL -- blocked on runtime redeploy
Validation quota:                                  1 of 2 CONSUMED (Independent Validation 1 = PASS)
Validation Round 2:                                NOT REQUIRED
REAL ANTHROPIC CALLS:                              0
DIAGNOSTIC ANTHROPIC CALLS:                         0
REASONING_LIVE_NETWORK_ENABLED:                    false
AT-D32 real requests consumed:                     1 of 12 (unchanged; retained by this record)
AT-D32 real requests remaining:                    11
Retained unresolved reservation:                   US$0.016086 (unchanged; retained by this record)
Budget policy:                                     inactive
AT-M4:                                             NOT AUTHORIZED
Production:                                        NOT GRANTED
production_executed_true_count:                    0
```

## 1. What this record accepts

AT-D36 authorized one bounded remediation: remove the top-level `temperature` field from the
outbound Claude Sonnet 5 Messages request, and retire the now-dead `GENERATION_TEMPERATURE` /
`GenerationProfile.temperature` configuration behind it. That remediation was implemented on branch
`at-m3.6b.2-sonnet5-request-contract-remediation-1`, ending at commit `d1deae9`, and was independently
validated by a fresh, read-only Independent Implementation Validation session
(`AT-M3.6B.2-SONNET-5-REQUEST-CONTRACT-INDEPENDENT-VALIDATION-1`), which returned **PASS** on its
first round. This record accepts that result and authorizes the merge. No second validation round was
required or used.

## 2. Accepted implementation candidate

```text
implementation_end   d1deae9aa0f0b47ba2a68dbaec9c1aab4dd04451
branch               at-m3.6b.2-sonnet5-request-contract-remediation-1
commit               d1deae9  fix(at-m3.6b.2) -- remove sampling parameter from Sonnet 5 request (AT-D36)
diff vs main         4 files, +46, -14
                     shared/sdk/agent_reasoning/anthropic_provider.py
                     shared/sdk/agent_reasoning/live_config.py
                     tests/test_at_m3_6b_1_anthropic_adapter.py
                     tests/test_at_m3_6b_1_config_and_egress.py
```

No file under `apps/`, `migrations/`, `infra/`, `shared/sdk/llm_budget/`, `shared/sdk/secrets/`, or
the `ReasoningService` implementation was touched. Nothing outside the four files above changed.

## 3. Validation history, recorded as it happened

```text
Independent Validation 1 / 2    PASS
    Base defect independently reproduced by direct inspection of the pre-remediation blob: a
    top-level "temperature": profile.temperature (= GENERATION_TEMPERATURE = 0.2) was present in
    build_request()'s return payload; top_p and top_k were confirmed absent on base.
    Candidate independently proven to omit temperature/top_p/top_k from the payload reaching the
    injected transport, for all four authorized verbs (propose, critique, summarize_decision,
    decompose_plan), through the real AnthropicReasoningProvider request-builder path (no synthetic
    alternate constructor).
    Non-regression independently confirmed for model, endpoint, headers, messages/system, max_tokens,
    retry/replay authority, budget reservation/settlement, and credential handling -- all 0-line diff
    outside the four named files.
    Official current Sonnet 5 documentation independently checked (platform.claude.com, live
    fetch): non-default temperature/top_p/top_k values return HTTP 400; omitting the parameter is
    explicitly the accepted, recommended migration path. Confirms the remediation premise.
    Deterministic test reproduction: 298 passed, 0 candidate-caused failures, across the adapter,
    config/egress, service-contract, retry-authority, budget-reservation, network-proof, bounds and
    compatibility, safety-surface, migration, and relevant M3.1/M3.4 durability suites (remaining
    tests SKIPPED -- no local Postgres in the validation environment). One pre-existing failure
    (tests/test_at_m3_4_planning_decision_api.py::test_an_unknown_planning_decision_is_a_404_on_every_read_route)
    was independently reproduced identically against the unmodified base commit and classified
    PRE_EXISTING / ENVIRONMENT / NON_BLOCKING -- not a candidate regression.
    ruff and black clean on all four changed files. mypy clean on the two changed implementation
    files; four pre-existing union-attr findings in shared/sdk/agent_team/store.py (0-line diff vs
    base, unrelated path) classified PRE_EXISTING / NON_BLOCKING.
    Secret-scan critical finding at scripts/verify_step66c4_be3_ra1d_missing_config_json.py:129
    independently classified as a synthetic test-fixture DSN (fake user/password, loopback host,
    deliberately unreachable port), not a real credential -- PRE_EXISTING / NON_BLOCKING, file
    untouched by candidate.
    Zero real Anthropic calls, zero diagnostic calls, live gate false throughout, budget policy
    inactive throughout, production count 0.

Validation quota                1 of 2 CONSUMED
Validation Round 2               NOT REQUIRED
```

## 4. Accepted technical state

```text
Outbound Sonnet 5 payload   {model, max_tokens, system, messages} -- temperature/top_p/top_k absent
GENERATION_TEMPERATURE      retired -- removed from shared/sdk/agent_reasoning/live_config.py, not
                                 set to None-and-serialized
GenerationProfile.temperature  retired -- field removed from the dataclass
Reasoning provider           anthropic
Reasoning model               claude-sonnet-5
reasoning_live_enabled        false
Real Anthropic calls (this record)         0
Diagnostic Anthropic calls (this record)   0
production_executed_true_count             0
```

## 5. What accepting this remediation does NOT mean

```text
Does NOT mean AT-M3.6B.2 Live Validation has succeeded -- it has not been retried
Does NOT mean the runtime can serve a live call -- the deployed runtime checkout (158c8a8) is
   independently confirmed NOT an ancestor of this candidate, so it does not contain this fix
Does NOT release, settle, or alter the retained US$0.016086 reservation from the prior HTTP-400
   attempt -- it remains retained, unresolved, and unchanged
Does NOT reactivate the AT-D33/AT-D35 budget policy -- it remains inactive
Does NOT resolve the deferred HTTP 400 -> provider_unauthorized taxonomy gap -- still CONFIRMED /
   DEFERRED / NON_BLOCKING_FOR_REQUEST_CONTRACT_REMEDIATION
Does NOT authorize a structured-output migration -- still DEFERRED / NON_BLOCKING
Does NOT authorize shared test-DB isolation work -- still PRE_PRODUCTION / NON_BLOCKING
Does NOT authorize AT-M3.5, AT-M4, HumanApproval mutation, or production action
```

## 6. Merge authorization

```text
Method              git merge --ff-only
Result              main advanced fc9608d -> d1deae9, no merge commit, no rebase, no squash, no
                        cherry-pick, no force push, no candidate alteration
Reconciliation      docs/governance only -- this record, AI_AGENTS_PM_STATE.md, source/progress.md,
                        committed separately on top of the fast-forwarded tip
Guarded trees       apps/ shared/ agents/ migrations/ infra/ scripts/ tests/ MUST be byte-identical
                        between implementation_end (d1deae9) and the reconciliation tip
```

`AT_M3_6B_2_SONNET_5_REQUEST_CONTRACT_REMEDIATION_IMPLEMENTATION_END` names `d1deae9`, the exact
independently validated commit, and does not follow past it. The reconciliation commit that lands on
top is documentation and never carried validation coverage.

## 7. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B.2 Live Validation execution, or any part of it
Does NOT authorize a real external call of any kind, official or diagnostic
Does NOT authorize enabling REASONING_LIVE_NETWORK_ENABLED, not even briefly
Does NOT authorize reactivating the AT-D33/AT-D35 budget policy
Does NOT authorize reading, validating, rotating or re-provisioning ANTHROPIC_API_KEY, or any Vault
   query for its value
Does NOT authorize any runtime rebuild, redeploy, restart, or Vault mutation
Does NOT authorize a FailureCategory addition, a migration, or any taxonomy change
Does NOT authorize a structured-output migration to output_config.format
Does NOT authorize AT-M4 or any real work execution
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT amend AT-D32, AT-D33, AT-D34, AT-D35 or AT-D36
Does NOT claim the runtime or the product is production-ready in any respect
```

## 8. Next decision

`AT-M3.6B.2 Sonnet 5 Request Contract Runtime Image Redeploy` — the deployed test-runtime image must
be rebuilt from this new canonical `main` (containing `d1deae9`) before any further Live Validation
attempt; the existing image (`158c8a8`) must not serve another live call. After that redeploy, a
**fresh** budget-policy reactivation authorization and a **fresh** AT-D32-bounded Live Validation
execution session are still required before any real Anthropic request is attempted again. Nothing in
this record supplies any of them.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
