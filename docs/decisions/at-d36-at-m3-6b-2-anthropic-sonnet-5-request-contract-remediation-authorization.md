# AT-D36 — AT-M3.6B.2 Anthropic Sonnet 5 Request Contract Remediation Authorization

> **Product Owner decision record. Authorizes ONE bounded implementation remediation: removing the
> prohibited sampling parameter `temperature` from the canonical Claude Sonnet 5 Messages request
> emitted by `AnthropicReasoningProvider`, and retiring the now-dead generation configuration behind
> it. It authorizes NO Anthropic call, NO live-gate enablement, NO budget-policy change, NO
> credential access, NO failure-taxonomy change, NO migration, and NO runtime deployment.
> `production_executed_true_count: 0`.**

```text
AT-D36:                      RESOLVED / BINDING
Recorded_on:                 2026-09-10
Recorded_by:                 Product Owner
Canonical_main_at_decision:  92d7fa78f4e0bef78f7d7e33882d8b96cf23d0e1
Branch:                      (docs-only, direct to main)
Depends_on:                  AT-D32 (docs/decisions/at-d32-at-m3-6b-2-live-validation-authorization.md)
                             AT-D33 (docs/decisions/at-d33-at-m3-6b-2-live-validation-budget-policy-provisioning-authorization.md)
                             AT-D34 (docs/decisions/at-d34-at-m3-6b-2-test-runtime-database-migration-alignment-authorization.md)
                             AT-D35 (docs/decisions/at-d35-at-m3-6b-2-live-validation-budget-policy-reactivation-authorization.md)

IMPLEMENTATION REMEDIATION:              AUTHORIZED
THIS SLICE:                              AUTHORIZED
ANTHROPIC CALLS AUTHORIZED BY THIS RECORD: 0
REASONING_LIVE_NETWORK_ENABLED:          false throughout -- not touched by this record
BUDGET POLICY:                           inactive throughout -- not touched by this record
AT-M4:                                   NOT AUTHORIZED
Production:                              NOT GRANTED
production_executed_true_count:          0
```

## 1. What this record is for

The AT-M3.6B.2 Live Validation execution session authorized by AT-D32 ran, reached
`https://api.anthropic.com/v1/messages`, and returned **HTTP 400** on its first and only real
request. It produced zero reasoning artifacts. The session's own report hypothesised that the cause
was "most likely the API key or its format".

A subsequent fresh read-only design review
(`AT-M3.6B.2-ANTHROPIC-SONNET-5-REQUEST-COMPATIBILITY-DESIGN-REVIEW-1`) tested that hypothesis
against the official Anthropic Messages API contract and against canonical source, and found it
**not supported**. The review identified a deterministic local request-contract defect that fully
explains the 400 without reference to the credential. This record authorizes fixing exactly that
defect, and nothing else.

## 2. The accepted deterministic finding

```text
Defect:                        AnthropicReasoningProvider.build_request() unconditionally emits a
                                top-level "temperature" field in the Anthropic Messages request body.
                                Its value is the fixed constant GENERATION_TEMPERATURE = 0.2, carried
                                via GenerationProfile.temperature, for every reasoning verb.
Contract:                      Claude Sonnet 5 REMOVED sampling parameters. `temperature`, `top_p`
                                and `top_k` are rejected with HTTP 400 invalid_request_error. The
                                authorized model claude-sonnet-5 is subject to this.
Consequence:                   every request this adapter can build is rejected deterministically.
                                The observed 1-of-12 HTTP 400 is fully accounted for.
Status semantics:              HTTP 400 is invalid_request_error (malformed/unsupported request).
                                HTTP 401 is authentication_error (malformed, expired, or revoked key).
                                A credential fault would have surfaced as 401, not 400.
Credential:                    NOT inspected, NOT implicated. CREDENTIAL_ROTATION_NOT_JUSTIFIED.
                                The credential is resolved LAST, immediately before the wire; a
                                missing or unusable secret refuses without any HTTP request at all,
                                so the fact that a real request reached the API and was evaluated as
                                a request is positive evidence the credential resolved.
Fields verified ABSENT:        top_p, top_k, thinking/budget_tokens, assistant-message prefill,
                                tools, tool_choice -- none of the other known Sonnet 5 breaking
                                changes is present in the canonical request.
Fields verified CORRECT:       endpoint /v1/messages, model claude-sonnet-5, anthropic-version
                                header, max_tokens (1500 / 4000 by verb), single user message with
                                top-level system string.
```

## 3. Authorized scope

```text
1. shared/sdk/agent_reasoning/anthropic_provider.py
     Remove "temperature" from the Anthropic Messages request payload built by build_request().
     After the change the outbound body MUST contain none of: temperature, top_p, top_k.

2. shared/sdk/agent_reasoning/live_config.py
     Retire/remove GENERATION_TEMPERATURE and GenerationProfile.temperature, including the
     related dataclass field, generation_profile() construction, type annotations, docstrings and
     comments. Dead configuration is REMOVED rather than retained: a configured sampling value that
     cannot legally be sent is an attractive misconfiguration trap for the next reader.
     Setting temperature=None and continuing to serialize it is explicitly NOT acceptable -- the
     field must be ABSENT from the outbound payload.

3. Direct Anthropic adapter/provider tests required to protect this request contract.
     The existing assertion `payload["temperature"] == 0.2` asserts the defect and must be replaced
     with positive contract protection.

Required regression rule:      for every authorized reasoning verb -- propose, critique,
                                summarize_decision, decompose_plan -- the canonical request payload
                                for claude-sonnet-5 contains NONE of: temperature, top_p, top_k.
                                Proven by request-builder inspection or an injected in-process
                                transport. No network socket. No real credential.

Environment:                    repository only. Local deterministic test execution only.
```

## 4. Explicitly deferred — the HTTP 400 failure-taxonomy defect

The same design review confirmed a second, separate defect: `_http_failure_category()` maps every
`4xx` to `provider_unauthorized`, so HTTP 400 is recorded as an authorization failure. That mapping
is what redirected the previous investigation onto the credential.

```text
Classification:                 CONFIRMED / SEPARABLE / NON_BLOCKING_FOR_THIS_FIX / DEFERRED
Why deferred:                   correcting it requires a new FailureCategory member plus a forward
                                and down migration amending chk_reasoning_invocations_failure_category
                                (migration 044). That touches the canonical taxonomy and the schema.
                                It is not required for a Sonnet 5 request to be ACCEPTED, and
                                retryability is already correct today -- provider_unauthorized is
                                outside RETRYABLE_FAILURE_CATEGORIES, so the mis-label did not cause
                                a retry and did not multiply spend.
NOT authorized by this record:  provider_invalid_request, provider_contract_error, or any new
                                FailureCategory; any change to FAILURE_CATEGORIES,
                                RETRYABLE_FAILURE_CATEGORIES, migration 044, or the
                                reasoning_invocations failure-category CHECK constraint; any new
                                migration.
```

The structured-output mechanism is likewise deferred: the review classified the existing
prompt-embedded JSON Schema plus strict client-side parser as **valid but suboptimal**, and
explicitly **not** the HTTP 400 root cause. Migration to `output_config.format` is NOT authorized
here and must not be undertaken opportunistically.

## 5. What is NOT authorized

```text
Any Anthropic call, real or diagnostic                   0 authorized by this record
REASONING_LIVE_NETWORK_ENABLED = true, anywhere          NOT authorized
Budget-policy activation, or any llm_budget_policies write  NOT authorized -- policy stays inactive
Release, settlement, deletion or rewrite of the retained
  US$0.016086 reservation or any prior live-attempt
  budget evidence                                        NOT authorized -- it is spend evidence
Reading, validating, rotating or re-provisioning
  ANTHROPIC_API_KEY; any Vault query for the key value;
  inspecting the x-api-key header value                  NOT authorized
FailureCategory / taxonomy / migration changes           NOT authorized -- deferred, see section 4
Structured-output migration to output_config.format      NOT authorized -- deferred, see section 4
ReasoningService retry semantics, MAX_ATTEMPTS,
  lease/takeover, replay, reservation or settlement
  behavior                                               NOT authorized to change
BudgetPolicyStore, SecretProvider, Vault scripts         NOT authorized to change
Runtime image rebuild or redeploy                        NOT authorized in this stage
Test-DB pollution cleanup (26 fake live rows,
  4 dangling STARTED)                                    NOT authorized here -- separate P2 stage
AT-M3.5, AT-M4, HumanApproval, production                NOT authorized
Merging the implementation candidate to main             NOT authorized by this record
```

## 6. Validation and acceptance split

This record authorizes IMPLEMENTATION only. It is not acceptance.

```text
Implementation session:         produces a candidate branch and pushes it. Does NOT merge to main,
                                does NOT self-declare acceptance, does NOT rebuild or redeploy the
                                runtime.
Next stage:                     AT_M3_6B_2_SONNET_5_REQUEST_CONTRACT_INDEPENDENT_VALIDATION_1 --
                                a separate, fresh Independent Implementation Validation session.
Then:                           a further, separate Product Owner acceptance and merge authorization,
                                matching every prior AT-M3.6B.2 implementation/acceptance split.
Runtime:                        RUNTIME_REDEPLOY_REQUIRED_AFTER_CANONICAL_ACCEPTANCE = YES. This
                                change is inside shared/sdk/, which the runtime image carries. The
                                existing runtime checkout/image MUST NOT be used for another Live
                                Validation attempt.
```

## 7. AT-D32 remains independently binding, unchanged and unconsumed by this record

AT-D32's envelope is untouched. One of its twelve authorized real requests has been consumed and
returned HTTP 400; eleven remain. This record does not reset, expand, pre-consume, or re-authorize
any part of that envelope, and consumes zero of it: this stage and the implementation it authorizes
make **zero** Anthropic calls and spend **US$0**.

## 8. What this decision does NOT do

```text
Does NOT authorize any Anthropic call, real or diagnostic
Does NOT authorize live-gate enablement
Does NOT authorize budget-policy reactivation, or any budget mutation
Does NOT authorize credential access of any kind
Does NOT authorize a new FailureCategory or any migration
Does NOT authorize a structured-output migration
Does NOT authorize runtime rebuild or redeploy
Does NOT authorize merging the candidate to main
Does NOT authorize AT-M4 or any real work execution
Does NOT constitute acceptance of the implementation it authorizes
Does NOT claim the prior HTTP 400 had any cause other than the recorded request-contract defect,
  and does NOT foreclose a spend-limit hypothesis should the remediated request still return 400
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
