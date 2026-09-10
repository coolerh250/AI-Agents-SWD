# AT-D40 — AT-M3.6B.2 Critique ValidationError Safe Diagnostic Metadata Remediation Authorization

> **Product Owner decision record. Authorizes ONE bounded implementation remediation: capturing
> safe, schema-only Pydantic validation-error metadata (field path and violation type — never a
> value, never raw provider output) into the sanitized failure detail already produced by
> `AnthropicReasoningProvider._parse()` on a `malformed_output` outcome. It authorizes NO Anthropic
> call, real or diagnostic, NO live-gate enablement, NO budget-policy change, NO credential access,
> NO schema change to any reasoning artifact, NO critique prompt change, NO failure-taxonomy change,
> NO migration, and NO runtime deployment. `production_executed_true_count: 0`.**

```text
AT-D40:                      RESOLVED / BINDING
Recorded_on:                 2026-09-10
Recorded_by:                 Product Owner
Canonical_main_at_decision:  310a787e3b4acb29c50fdb0c1048fd18a27df004
Branch:                      (docs-only, direct to main)
Depends_on:                  AT-D32 (docs/decisions/at-d32-at-m3-6b-2-live-validation-authorization.md)
                             AT-D36 (docs/decisions/at-d36-at-m3-6b-2-anthropic-sonnet-5-request-contract-remediation-authorization.md)
                             AT-D37 (docs/decisions/at-d37-at-m3-6b-2-sonnet-5-request-contract-product-acceptance-and-merge-authorization.md)
                             AT-D38 (docs/decisions/at-d38-at-m3-6b-2-runtime-image-redeploy-evidence-reconciliation.md)
                             AT-D39 (docs/decisions/at-d39-at-m3-6b-2-live-validation-execution-combined-budget-activation-and-terminal-cleanup-authorization.md)

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

The AT-D39-authorized combined execution session ran. Per its own record, it produced:

```text
propose:              PASS
same-correlation replay: PASS / 0 additional provider calls
decompose_plan:        PASS / durable PlanDraftArtifact / not dispatched
critique:              HTTP 200 / provider=anthropic / model=claude-sonnet-5 / terminal
                       failure_category=malformed_output / CritiqueArtifact NOT persisted
summarize_decision:    PASS
```

A subsequent fresh read-only design review
(`AT-M3.6B.2-CRITIQUE-ARTIFACT-COMPATIBILITY-DESIGN-REVIEW-1`) root-caused the critique failure
using only safe, durable evidence: a bounded read-only Postgres `SELECT` of non-content columns on
the failed correlation, and an offline, no-network local reproduction against the canonical
`CritiqueArtifact` Pydantic model. That review found:

```text
Correlation:            65496538-621c-4c22-99e0-f510507b358f
HTTP:                   200 (call reached the wire, was billed, and settled)
attempt:                1 (malformed_output is not retryable; correctly terminal)
input/output tokens:    624 / 671, against a 1500-token ceiling (44.7%) -- not near truncation,
                        and in the same range as the successful decompose_plan (44.25% of its
                        4000-token ceiling)
Persisted failure text: "the live reasoning response does not satisfy CritiqueArtifact
                        (ValidationError)" -- reachable ONLY after json.loads() succeeds
```

Local reproduction against the real model confirmed that markdown fencing, truncation, and
prose-before-JSON all produce a *different* persisted message (`"...is not valid JSON
(JSONDecodeError)"`) than what was actually recorded. This deterministically **rules out**
truncation, markdown framing, and prose preamble as the cause. It **confirms** the response was a
complete, syntactically valid JSON object that failed Pydantic schema validation against
`CritiqueArtifact` -- a missing field, wrong type, forbidden extra field, or bound violation.

The review could not identify *which* of those four occurred, because
`AnthropicReasoningProvider._parse()` currently persists only the exception's class name
(`ValidationError`) into the sanitized failure detail, discarding Pydantic's own `errors()` output
-- which carries safe, schema-only `loc`/`type` pairs (field paths and violation kinds), never a
value and never raw provider text.

This record authorizes closing exactly that diagnostic gap, and nothing else.

## 2. Authorized scope

```text
1. shared/sdk/agent_reasoning/anthropic_provider.py
     In `_parse()`'s existing ValidationError except-branch only: capture Pydantic's
     `exc.errors()` and derive a bounded, sanitized diagnostic string from it, appended to (or
     replacing the generic suffix of) the existing LiveProviderError message for this branch only.
     A small private helper function in the SAME module, used only to build this sanitized string,
     is authorized if mechanically convenient. No other function, and no other exception branch in
     `_parse()`, may change behavior.

2. Direct adapter/provider tests required to protect this diagnostic contract, added or changed
     in the existing test files for this slice (e.g. tests/test_at_m3_6b_1_anthropic_adapter.py).

Required contract, binding on the implementation:
   - failure_category remains "malformed_output" for every case already mapped to it. No new
     FailureCategory. No taxonomy change.
   - The success path (a response that validates) is byte-for-byte, semantically unchanged.
   - Every OTHER malformed_output trigger in _parse() (no content blocks, empty text, invalid
     JSON, JSON not an object, oversized-artifact backstop) is UNCHANGED -- this record touches
     only the branch reached after json.loads() succeeds and model_validate() then raises.
   - Trusted field names may be surfaced only when they are drawn from the artifact's own
     Pydantic model (e.g. via `artifact_type.model_fields`), never persisted verbatim from
     provider-controlled input. An unrecognised/provider-invented field-name segment in a `loc`
     path is normalized to a fixed placeholder (e.g. "<extra-field>"); a numeric/list-index
     segment is normalized to a fixed placeholder (e.g. "<index>"). No raw string segment that
     did not originate from the local schema may be persisted verbatim.
   - The diagnostic representation is bounded: a fixed maximum count of individual field errors
     represented (this record sets that ceiling at 8, chosen by the implementation as
     unremarkable and documented in code and tests) and a fixed maximum serialized length for the
     whole diagnostic string. Exceeding either bound truncates deterministically; it never grows
     unbounded.
   - `errors()["input"]`, `errors()["ctx"]`, the full untruncated Pydantic message, any provider
     response value, the raw completion, the response body, the request body, headers, or any
     credential MUST NOT be persisted in any form, sanitized or not.
   - No DB schema change and no migration. If the existing `LiveProviderError`/failure_reason
     contract only carries a string, the bounded diagnostic is serialized deterministically into
     that existing string field -- no new persistence model.

Environment:                    repository only. Local deterministic test execution only, using an
                                 injected in-process transport. No network socket. No real
                                 credential.
```

## 3. Explicitly out of scope for this record

This record is a diagnostics-only remediation. It does not attempt to fix, and does not assume the
cause of, the critique failure itself. The following remain **unchanged and unauthorized here**:

```text
CritiqueArtifact, ProposalArtifact, PlanDraftArtifact, DecisionSummaryArtifact schemas  NOT AUTHORIZED
Critique prompt / system prompt / user-message construction / _VERB_TASK text          NOT AUTHORIZED
Structured-output migration (output_config.format)                                     NOT AUTHORIZED -- deferred, unchanged
FailureCategory / malformed_output taxonomy / any migration                            NOT AUTHORIZED
HTTP 400 -> provider_unauthorized taxonomy gap (AT-D36 section 4)                       NOT AUTHORIZED -- unchanged, still deferred
build_request(), model/endpoint/headers, temperature/top_p/top_k handling              NOT AUTHORIZED to change
ReasoningService retry/replay/lease/takeover semantics                                 NOT AUTHORIZED to change
BudgetPolicyStore, SecretProvider, Vault, any budget mutation                          NOT AUTHORIZED
Any Anthropic call, real or diagnostic                                                 0 authorized by this record
REASONING_LIVE_NETWORK_ENABLED = true, anywhere                                        NOT authorized
Runtime image rebuild or redeploy                                                      NOT authorized in this stage
Merging the implementation candidate to main                                           NOT authorized by this record
AT-M3.5, AT-M4, HumanApproval mutation, production action                              NOT authorized
```

The validation-harness procedural finding (summarize_decision run immediately after critique's
malformed_output, with no observed STOP) is recorded as `P3 / PROCEDURAL / VALIDATION-HARNESS /
NON_P0_P1` and is NOT remediated by this record. No production `ReasoningService` behavior change is
authorized for it.

## 4. Validation and acceptance split

This record authorizes IMPLEMENTATION only. It is not acceptance.

```text
Implementation session:   produces a candidate branch based on this record's own canonical main and
                           pushes it. Does NOT merge to main, does NOT self-declare acceptance, does
                           NOT rebuild or redeploy the runtime.
Next stage:                AT_M3_6B_2_CRITIQUE_VALIDATIONERROR_SAFE_DIAGNOSTIC_METADATA_INDEPENDENT_VALIDATION_1
                           -- a separate, fresh Independent Implementation Validation session.
Then:                      a further, separate Product Owner acceptance and merge authorization,
                           matching every prior AT-M3.6B.2 implementation/acceptance split.
```

## 5. AT-D32's envelope remains independently binding, unchanged and unconsumed by this record

AT-D32's lifetime envelope (5 of 12 real requests consumed, 7 remaining; effective validation cost
US$0.060134; budget policy inactive; live gate false; `production_executed_true_count: 0`) is
preserved exactly as reported by the AT-D39-authorized execution. This record consumes **zero** of
it: it makes no Anthropic call, real or diagnostic, and mutates no budget, gate, or credential
state.

## 6. What this decision does NOT do

```text
Does NOT authorize any Anthropic call, real or diagnostic
Does NOT authorize live-gate enablement or budget-policy mutation
Does NOT authorize credential access of any kind
Does NOT authorize a schema change to any reasoning artifact
Does NOT authorize a critique prompt change
Does NOT authorize a new FailureCategory, a taxonomy change, or any migration
Does NOT authorize a structured-output migration
Does NOT authorize runtime rebuild or redeploy
Does NOT authorize merging the candidate to main
Does NOT authorize AT-M4 or any real work execution
Does NOT constitute acceptance of the implementation it authorizes
Does NOT claim the exact CritiqueArtifact violation is known -- it authorizes the mechanism that
   would reveal it on a future occurrence, without asserting what that occurrence will show
Does NOT invalidate the already-proven propose / replay / decompose_plan / summarize_decision
   evidence from the AT-D39-authorized execution
```

## 7. Next decision

`AT_M3_6B_2_CRITIQUE_VALIDATIONERROR_SAFE_DIAGNOSTIC_METADATA_INDEPENDENT_VALIDATION_1` — a
separate, fresh Independent Implementation Validation session against the candidate branch this
record authorizes. Any future critique-only live revalidation remains a separate, later
authorization and is not implied or granted here.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
