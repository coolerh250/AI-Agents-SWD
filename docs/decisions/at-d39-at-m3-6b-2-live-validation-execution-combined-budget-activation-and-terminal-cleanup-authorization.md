# AT-D39 — AT-M3.6B.2 Live Validation Execution — Combined Budget Activation and Terminal Cleanup Authorization

> **Product Owner decision record. Authorizes ONE bounded combined execution: reactivating the
> already-provisioned AT-D33/AT-D35 budget policy strictly inside this session, running the
> AT-D32-bounded live validation (propose → same-correlation replay → decompose_plan, with
> critique/summarize_decision only if the full remaining envelope permits), and returning the
> policy to inactive as one bounded transaction before the session ends. Authorizes NO
> implementation patch, NO migration, NO runtime rebuild/redeploy, NO credential change, NO
> failure-taxonomy remediation, NO structured-output redesign, NO AT-M3.5 dispatch, NO AT-M4, NO
> HumanApproval mutation, and NO production action. `production_executed_true_count: 0`.**

```text
AT-D39:                      RESOLVED / BINDING
Recorded_on:                 2026-09-10
Recorded_by:                 Product Owner
Canonical_main_at_decision:  6818111b38488002520159d995c6fbd8fdd492b4 (unchanged by this record)
Depends_on:                  AT-D32, AT-D33, AT-D34, AT-D35, AT-D36, AT-D37, AT-D38
Scope:                        Docs-only combined-execution authorization. No implementation, no
                               runtime mutation, no budget-policy mutation performed BY this record.

AT-M3.6B.2 RUNTIME IMAGE:    REDEPLOYED / VERIFIED / CLOSED (AT-D38, unchanged)
AT-M3.6B.2 LIVE VALIDATION:  AUTHORIZED / EXECUTION_READY
AT-D32 real requests:        1 of 12 CONSUMED (unchanged; this record performs 0)
AT-D32 requests remaining:   11
Retained unresolved reservation: US$0.016086 (unchanged; NOT released/settled/reset by this record)
Budget policy (d29ad073-9f7c-48b4-876d-cd3cb1343b40): INACTIVE at decision time; combined
                               activation authorized strictly inside the next execution session only
LIVE_NETWORK_GATE:           DEFAULT FALSE (unchanged by this record)
Real Anthropic calls (this record): 0
AT-M4:                       NOT AUTHORIZED
Production:                  NOT GRANTED
production_executed_true_count: 0
```

## 1. What this record does

AT-D38 independently re-verified, from the running non-production test orchestrator, that the
runtime image redeploy carrying the AT-D37 Sonnet 5 request-contract remediation actually occurred
and actually serves the fixed request path. That was the last open runtime prerequisite named by
AT-D32/AT-D36/AT-D37. AT-D38 section 5 named the next decision explicitly: this combined-execution
authorization, still requiring its own separate AT-D before any budget-policy activation or
Anthropic call. This record supplies that authorization. It does not itself activate the policy,
enable the live gate, or make any Anthropic call — it authorizes a following execution session to
do so, bounded exactly as below, as one transaction that must end with the policy back at
`inactive` regardless of outcome.

## 2. Authorized scope (restates and does not widen AT-D32)

```text
Provider:                    anthropic ONLY
Model:                        claude-sonnet-5 ONLY
Environment:                  internal non-production test runtime only
Allowed verbs:                propose, critique, summarize_decision, decompose_plan
Lifetime real Anthropic requests: <= 12 total (1 already consumed; 11 remain in this record's
                               envelope, unchanged from AT-D32)
Lifetime authorization attempts: <= 12 total (conservatively tracked alongside requests)
Maximum total AT-D32 effective validation cost: US$5.00 (settled actual + all unresolved retained
                               reservations, including the preserved US$0.016086)
Maximum cost per provider attempt: US$0.50
Maximum cost per correlation: US$1.50, maximum 3 attempts per correlation
Retry authority:              ReasoningService only -- no manual, HTTP-client, SDK, or operator retry
Mandatory sequence:           propose, then a same-correlation replay of that same propose
                               correlation (must add zero external calls), then decompose_plan
                               (validated only, never dispatched). critique and summarize_decision
                               are executed only if, immediately before each one, the full
                               remaining 3-attempt / US$1.50 worst-case envelope still fits every
                               applicable ceiling (lifetime requests, AT-D32 effective cost, daily
                               cap, monthly cap) -- otherwise each is recorded
                               NOT_EXECUTED_DUE_TO_AUTHORIZED_ENVELOPE, which is not a failure
Live gate:                    REASONING_LIVE_NETWORK_ENABLED=true authorized ONLY inside a bounded
                               ephemeral process against the existing aligned orchestrator
                               container/code/network (e.g. `docker compose exec -T -e
                               REASONING_LIVE_NETWORK_ENABLED=true orchestrator <ephemeral
                               validation process>`). The long-lived orchestrator service
                               environment remains REASONING_LIVE_NETWORK_ENABLED=false throughout
                               and after. No .env edit, no Compose edit, no rebuild, no redeploy,
                               no force-recreate
Budget policy activation:     the exact existing policy d29ad073-9f7c-48b4-876d-cd3cb1343b40 (no
                               new policy, no property change) may transition inactive -> active
                               strictly inside the execution session, and MUST transition back to
                               inactive before the session's terminal result is returned, regardless
                               of PASS/FAIL/BLOCKED/ABORT/DESIGN_REVIEW_REQUIRED. Activation and
                               terminal deactivation are one bounded transaction, not two separately
                               authorized actions
Credential use:                ONLY through ReasoningService -> AnthropicReasoningProvider ->
                               SecretProvider -> Vault KV v2 -> ANTHROPIC_API_KEY. Value, prefix,
                               length and hash never rendered, logged, or recorded
Data egress:                   locally-authored synthetic non-production reasoning content only
Durable persistence:           canonical structured reasoning artifacts and required safe
                               metadata/usage/cost evidence only -- no raw completion, no hidden
                               CoT, no authorization header, no credential, no unsanitized payload
```

## 3. Git/GitHub mutation during the execution session

```text
NOT AUTHORIZED during the live-call execution session itself (identical restriction to AT-D32
    section 3): commit, push, merge, tag, release, or any other repository mutation once the
    session moves past this record's own pre-execution commit.
This record's own commit (this file plus the PM-state/progress.md reconciliation below) is
    authorized and is the ONLY Git mutation before live calls begin.
Canonicalization of the execution's own result (report, evidence, any further PM-state/progress.md
    update reflecting what actually happened) is a SEPARATE, later Product Owner acceptance
    decision -- the same pattern AT-D27/AT-D29/AT-D31/AT-D37 each used.
```

## 4. Abort conditions (restates AT-D32 section 4, unchanged)

```text
credential leakage; exact wire request count > 12 lifetime; conservative authorization attempt
count > 12 lifetime; effective AT-D32 validation cost > US$5.00; any single attempt cost >
US$0.50; any correlation cost > US$1.50; unexpected provider; unexpected model; automatic
fallback; unexpected external host/path; raw provider payload durably persisted; hidden CoT
persisted; budget reservation failure before a call; a potentially incurred call whose cost cannot
be conservatively represented; a same-correlation replay causing an external call; M3.5 dispatch
consumer activity; M4-shaped execution; HumanApproval mutation; production action;
production_executed_true_count != 0; the long-lived orchestrator's live gate becoming true; the
target budget policy found already active before this session's own activation step (that is a
GOVERNANCE_DRIFT_ALERT, P1, per the parent execution standard -- STOP, do not proceed to live
calls, return the policy to inactive if safely possible under this record's own terminal-cleanup
authority).

On any abort, or on the session ending for any reason: the ephemeral live gate must disappear, the
long-lived orchestrator must independently show REASONING_LIVE_NETWORK_ENABLED=false, and the
target budget policy must independently show status=inactive.
```

## 5. What is NOT authorized

```text
AT-M4 implementation or any real work execution           NOT AUTHORIZED
Tool/shell/code execution by runtime agents                NOT AUTHORIZED
M3.5 dispatch consumer / plan delegation / decompose_plan dispatch NOT AUTHORIZED
Git/GitHub action during the execution session (section 3) NOT AUTHORIZED
HumanApproval mutation                                     NOT AUTHORIZED
Production action                                          NOT AUTHORIZED
Production authorization                                   NOT GRANTED -- unchanged
Provider or model fallback / substitution                  NOT AUTHORIZED
Implementation patching during the validation session      NOT AUTHORIZED -- a defect STOPs and is
                                                             classified, not fixed mid-session
Long-lived Compose/.env edit, rebuild, redeploy, force-recreate NOT AUTHORIZED
Deleting or rewriting the retained US$0.016086 reservation or the ~30 fake test-DB rows described
    in AT-D38 section 3                                    NOT AUTHORIZED
Rendering the credential value, prefix, length, or hash at any point NOT AUTHORIZED
A second policy-activation cycle within the same session after terminal cleanup NOT AUTHORIZED
```

## 6. What this decision does NOT do

```text
Does NOT itself activate the budget policy, enable the live gate, or make any Anthropic call --
   0 real Anthropic calls, 0 budget-policy mutations performed by this record
Does NOT release, settle, reset, or delete the AT-D32 retained US$0.016086 reservation
Does NOT authorize a second live-validation session beyond the one bounded execution this record
   covers
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4, AT-M3.5 dispatch, or any real work execution
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT amend AT-D32, AT-D33, AT-D34, AT-D35, AT-D36, AT-D37, or AT-D38
Does NOT authorize any runtime image rebuild, redeploy, or long-lived environment change
Does NOT pre-accept the execution's result -- PASS, FAIL, BLOCKED, or DESIGN_REVIEW_REQUIRED all
   remain possible outcomes governed by docs/process/stop-conditions.md and
   AI_AGENTS_PROJECT_EXECUTION_STANDARD.md section 7, and the result requires its own separate
   Product Owner acceptance (AT_M3_6B_2_LIVE_VALIDATION_PRODUCT_ACCEPTANCE) before canonicalization
```

## 7. Next decision

`AT_M3_6B_2_LIVE_VALIDATION_PRODUCT_ACCEPTANCE` -- a separate, later Product Owner acceptance
decision that canonicalizes whatever the execution session actually reports (PASS, FAIL, BLOCKED,
or DESIGN_REVIEW_REQUIRED), exactly as AT-D27/AT-D29/AT-D31/AT-D37 each accepted their own
preceding implementation-authorization record's result. This record does not perform that
acceptance and does not update PM state beyond marking this authorization
`AUTHORIZED / EXECUTION_READY`.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
