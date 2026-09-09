# AT-D32 — AT-M3.6B.2 Live Validation Authorization

> **Product Owner decision record. Authorizes ONE bounded action: a single AT-M3.6B.2 Live
> Validation execution session against the real Anthropic API, through the already-canonical
> `ReasoningService` / `AnthropicReasoningProvider` / `SecretProvider` / Vault path, inside an
> ephemeral live-gate process only. It authorizes NO Git/GitHub mutation during that execution
> session, NO AT-M4, NO production action and NO HumanApproval mutation.
> `production_executed_true_count: 0`.**

```text
AT-D32:                      RESOLVED / BINDING
Recorded_on:                 2026-09-09
Recorded_by:                 Product Owner
Canonical_main_at_decision:  e820d5fff88d8955e1b947ce80afd4788b96d7f7
Branch:                      (docs-only, direct to main)
Depends_on:                  AT-D26 (docs/decisions/at-d26-at-m3-6b-2-runtime-secret-readiness-authorization.md)
                             AT-D27 (docs/decisions/at-d27-at-m3-6b-2-runtime-secret-readiness-acceptance-and-merge-authorization.md)
                             AT-D28 (docs/decisions/at-d28-at-m3-6b-2-runtime-image-alignment-authorization.md)
                             AT-D29 (docs/decisions/at-d29-at-m3-6b-2-runtime-image-alignment-ratification-and-merge-authorization.md)
                             AT-D30 (docs/decisions/at-d30-at-m3-6b-2-real-anthropic-secret-provisioning-authorization.md)
                             AT-D31 (docs/decisions/at-d31-at-m3-6b-2-real-anthropic-secret-provisioning-acceptance-and-merge-authorization.md)

AT-M3.6B.2 LIVE VALIDATION:              AUTHORIZED / NOT YET EXECUTED
THIS SLICE:                              AUTHORIZED
REAL ANTHROPIC CALLS AUTHORIZED (MAX):   12
REAL ANTHROPIC CALLS MADE BY THIS RECORD: 0
REASONING_LIVE_NETWORK_ENABLED:          false (default) -- ephemeral-only enablement authorized, see section 3
AT-M4:                                   NOT AUTHORIZED
Production:                              NOT GRANTED
production_executed_true_count:          0
```

## 1. What this record is for

AT-D27 section 4, AT-D29, and AT-D30 sections 3/5 all drew the same line from different sides:
provisioning a real Anthropic credential and spending it are different risks, and AT-M3.6B.2 Live
Validation needs its own explicit Product Owner decision naming provider, model, call count, cost
ceilings, allowed verbs, environment, gate enablement, credential use and abort conditions — no
previously discussed envelope counts by having been discussed.

This record supplies that decision. It authorizes exactly one bounded validation session, described
in full below, and nothing beyond it. It does not itself perform the validation — a separate
execution session runs it, and a further, separate Product Owner acceptance closes it, exactly as
every prior AT-M3.6B.2 slice split implementation-authorization from acceptance-and-merge.

## 2. Authorized scope

```text
Provider:                    anthropic ONLY, no fallback, no substitute
Model:                       claude-sonnet-5 ONLY, no fallback, no substitute
Environment:                 internal non-production test runtime only
Allowed verbs:                propose, critique, summarize_decision, decompose_plan -- no other verb
Maximum real Anthropic requests: 12 total, every attempt counted (success, timeout, retry, rate
                               limit, failed request, diagnostic request -- no uncounted request)
Maximum total validation cost: US$5.00 (settled actual + unresolved retained reservations)
Maximum cost per provider attempt: US$0.50
Canonical per-correlation ceiling: US$1.50, maximum 3 attempts per correlation
Retry authority:              ReasoningService only -- no manual, HTTP-client, SDK, or operator retry
Live gate:                    REASONING_LIVE_NETWORK_ENABLED=true authorized ONLY inside a bounded
                               ephemeral validation process/session using the existing aligned
                               orchestrator container/code/network (e.g.
                               `docker compose exec -T -e REASONING_LIVE_NETWORK_ENABLED=true
                               orchestrator <ephemeral validation process>`). The long-lived
                               orchestrator service environment remains
                               REASONING_LIVE_NETWORK_ENABLED=false throughout and after. No .env
                               edit, no Compose edit, no rebuild, no redeploy, no force-recreate.
Credential use:                ONLY through ReasoningService -> AnthropicReasoningProvider ->
                               SecretProvider -> Vault KV v2 -> ANTHROPIC_API_KEY. The credential
                               stays in Vault. Its value, prefix, length, and hash are never
                               rendered, logged, or recorded in any artifact, log, or conversation.
Data egress:                   locally-authored synthetic non-production control-plane reasoning
                               content only. No secrets, credentials, Vault tokens, production data,
                               customer data, raw audit history, hidden chain-of-thought, or internal
                               system-prompt dumps.
Durable persistence:           canonical structured reasoning artifacts and required safe
                               metadata/usage/cost evidence only. No raw completion, no hidden CoT,
                               no authorization header, no credential, no unsanitized provider
                               payload.
Required evidence:            at least one successful `propose`; a same-correlation replay adding
                               zero external calls; at least one successful `decompose_plan` (result
                               validated only, never dispatched); `critique` and
                               `summarize_decision` attempted if the remaining full 3-attempt
                               envelope permits, otherwise recorded as not executed rather than
                               forced.
```

## 3. Git/GitHub mutation during the execution session

```text
NOT AUTHORIZED during the live-call execution session itself:
    commit, push, merge, tag, release, or any other repository mutation.
The execution session may read repository state for its zero-call preflight and may run an
    ephemeral, uncommitted validation harness (deleted on exit where practical), but must not
    change canonical main while real calls are in flight or pending.
Canonicalization of the EXECUTION'S OWN result (the report, evidence, and any PM-state/progress
    update reflecting what actually happened) is a SEPARATE, later Product Owner acceptance
    decision -- the same acceptance-after-execution pattern AT-D27, AT-D29 and AT-D31 each used for
    their own preceding implementation-authorization record.
```

## 4. Abort conditions

Immediate STOP, terminate the ephemeral session, and do not retry manually, on any of:

```text
credential leakage; exact wire request count > 12; conservative authorization attempt count > 12;
effective validation cost > US$5.00; any single attempt cost > US$0.50; unexpected provider;
unexpected model; automatic fallback; unexpected external host/path; raw provider payload durably
persisted; hidden CoT persisted; budget reservation failure before a call; a potentially incurred
call whose cost cannot be conservatively represented; a same-correlation replay causing an external
call; M3.5 dispatch consumer activity; M4-shaped execution; HumanApproval mutation; production
action; production_executed_true_count != 0; the long-lived orchestrator's live gate becoming true.
```

After any abort, or after the session ends for any reason, the ephemeral live gate must disappear
and the long-lived orchestrator must independently verify `REASONING_LIVE_NETWORK_ENABLED=false`.

## 5. What is NOT authorized

```text
AT-M4 implementation or any real work execution      NOT AUTHORIZED
Tool/shell/code execution by runtime agents            NOT AUTHORIZED
M3.5 dispatch consumer / plan delegation / dispatch of a decompose_plan result NOT AUTHORIZED
Git/GitHub action during the execution session (see section 3) NOT AUTHORIZED
HumanApproval mutation                                 NOT AUTHORIZED
Production action                                      NOT AUTHORIZED
Production authorization                               NOT GRANTED -- unchanged
Provider or model fallback / substitution              NOT AUTHORIZED
Additional diagnostic provider probes beyond the named verbs NOT AUTHORIZED
Implementation patching during the validation session  NOT AUTHORIZED -- a provider/integration
                                                         defect STOPs and is classified, not fixed
                                                         mid-session
Long-lived Compose/.env edit, rebuild, redeploy, force-recreate NOT AUTHORIZED
Rendering the credential value, prefix, length, or hash at any point NOT AUTHORIZED
```

## 6. What this decision does NOT do

```text
Does NOT itself execute any part of AT-M3.6B.2 Live Validation -- it authorizes a future, separate
   execution session bounded exactly as above
Does NOT pre-accept the execution's result. A FAIL, BLOCKED, or DESIGN_REVIEW_REQUIRED outcome from
   that session is still possible and still governed by docs/process/stop-conditions.md and
   AI_AGENTS_PROJECT_EXECUTION_STANDARD.md section 7
Does NOT authorize a second live-validation session -- this record covers ONE bounded session; a
   further session needs its own authorization
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4 or any real work execution
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT amend AT-D26, AT-D27, AT-D28, AT-D29, AT-D30 or AT-D31
Does NOT authorize any runtime image rebuild, redeploy, or long-lived environment change
Does NOT claim the runtime or the product is production-ready in any respect
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
