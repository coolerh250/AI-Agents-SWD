# AT-D41 — AT-M3.6B.2 Critique ValidationError safe diagnostic metadata product acceptance and merge authorization

> **Product Owner decision record. Accepts the AT-M3.6B.2 Critique ValidationError safe diagnostic
> metadata remediation authorized by AT-D40, on the strength of a PASS Independent Implementation
> Validation, and authorizes its fast-forward merge to `main`. It accepts that
> `AnthropicReasoningProvider._parse()`'s `ValidationError` branch now appends a bounded, schema-only
> diagnostic (field path + violation kind, never a value) to the `malformed_output` failure message.
> It authorizes NO Anthropic call, NO live-gate enablement, NO budget-policy change, NO credential
> access, NO failure-taxonomy change, NO migration, and NO runtime deployment. The `critique` verb
> remains NOT revalidated against the live provider -- a fresh critique-only Live Validation attempt
> is still required and is NOT authorized by this record. `production_executed_true_count: 0`.**

```text
AT-D41:                      RESOLVED / BINDING
Recorded_on:                 2026-09-11
Recorded_by:                 Product Owner
Canonical_main_before_merge: 6cf72e9746145122b6a60b6a8cb7b24b6f946d46
Branch:                      at-m3.6b.2-critique-validationerror-safe-diagnostics-1
Implementation_end:          767c5b149ae8090345267ce83a0d39292618f50b
Depends_on:                  AT-D32 (docs/decisions/at-d32-at-m3-6b-2-live-validation-authorization.md)
                             AT-D39 (docs/decisions/at-d39-at-m3-6b-2-live-validation-execution-combined-budget-activation-and-terminal-cleanup-authorization.md)
                             AT-D40 (docs/decisions/at-d40-at-m3-6b-2-critique-validationerror-safe-diagnostic-metadata-remediation-authorization.md)

AT-M3.6B.2 CRITIQUE VALIDATIONERROR SAFE DIAGNOSTICS:  PO_ACCEPTED / MERGED / CANONICAL
AT-M3.6B.2 CRITIQUE COMPATIBILITY:                 DIAGNOSTIC_OBSERVABILITY_AVAILABLE / LIVE_CRITIQUE_REVALIDATION_REQUIRED
AT-M3.6B.2 LIVE VALIDATION:                        EXECUTED / PARTIAL_TECHNICAL_SUCCESS / CRITIQUE_REVALIDATION_PENDING
Validation quota:                                  1 of 2 CONSUMED (Independent Validation 1 = PASS)
Validation Round 2:                                NOT REQUIRED
REAL ANTHROPIC CALLS:                              0
DIAGNOSTIC ANTHROPIC CALLS:                         0
REASONING_LIVE_NETWORK_ENABLED:                    false
AT-D32 real requests consumed:                     5 of 12 (unchanged; retained by this record)
AT-D32 real requests remaining:                    7
AT-D32 effective validation cost:                  US$0.060134 (settled US$0.044048 + retained unresolved US$0.016086; unchanged, not recomputed or resettled by this record)
Retained unresolved reservation:                   US$0.016086 (unchanged; retained by this record)
Budget policy:                                     inactive
AT-M4:                                              NOT AUTHORIZED
Production:                                         NOT GRANTED
production_executed_true_count:                     0
```

## 1. What this record accepts

AT-D40 authorized one bounded remediation, confined to the existing `ValidationError` except-branch
of `AnthropicReasoningProvider._parse()`: a private helper (`_sanitize_validation_errors`) that
derives trusted field names only from the failing artifact's own `model_fields`, normalizes every
unrecognized or provider-controlled `loc` segment (root or nested, string or index) to a fixed
`<extra-field>` / `<index>` placeholder, reports Pydantic's own closed-vocabulary `type` string, caps
the result at 8 errors and 300 characters, and appends it to the existing `malformed_output` message.
That remediation was implemented on branch
`at-m3.6b.2-critique-validationerror-safe-diagnostics-1`, ending at commit `767c5b1`, and was
independently validated by a fresh, read-only Independent Implementation Validation session
(`AT-M3.6B.2-CRITIQUE-VALIDATIONERROR-SAFE-DIAGNOSTIC-METADATA-INDEPENDENT-VALIDATION-1`), which
returned **PASS** on its first round. This record accepts that result and authorizes the merge. No
second validation round was required or used.

## 2. Accepted implementation candidate

```text
implementation_end   767c5b149ae8090345267ce83a0d39292618f50b
branch               at-m3.6b.2-critique-validationerror-safe-diagnostics-1
commit               767c5b1  fix(at-m3.6b.2) -- capture safe schema-only validation-error
                              diagnostics (AT-D40)
diff vs main         2 files, +217, -1
                     shared/sdk/agent_reasoning/anthropic_provider.py
                     tests/test_at_m3_6b_1_anthropic_adapter.py
```

No file under `apps/`, `migrations/`, `infra/`, `shared/sdk/llm_budget/`, `shared/sdk/secrets/`, or
any other `ReasoningService`/store implementation was touched. Nothing outside the two files above
changed.

## 3. Validation history, recorded as it happened

```text
Independent Validation 1 / 2    PASS
    Candidate full SHA independently resolved from the remote branch (git ls-remote / rev-parse),
    not trusted from the short form. Ancestry independently confirmed: candidate descends directly
    from canonical base 6cf72e9, is not merged to main, working tree clean.
    Diff independently recomputed: exactly the two expected files, +217/-1, matching the reported
    size. No unexpected path. Success path, JSONDecodeError path, content-safety path, HTTP-failure
    path, build_request(), retry/replay authority, and budget code all independently confirmed
    untouched (0-line diff outside the ValidationError except-branch and the test file).
    Sanitizer inspected line-by-line: trusted field names derive only from artifact_type.model_fields
    checked at loc index 0; every other segment (unknown root, any nested segment, any list index)
    normalizes to a fixed placeholder; error `type` is Pydantic's own closed-vocabulary string; 8-error
    and 300-char bounds enforced with a value-free overflow marker; truncation happens only after
    normalization, so it cannot leak partial unsanitized content.
    64 validator-owned adversarial checks run independently (not part of the candidate's own suite)
    against real Pydantic ValidationErrors from CritiqueArtifact, ProposalArtifact,
    DecisionSummaryArtifact and PlanDraftArtifact: credential-shaped field names, long Unicode,
    RTL-override / newline / CR / tab / ANSI-escape / zero-width control characters, nested and
    unknown-root loc shapes, 0/1/8/9/100/1000-error counts, and a direct check that Pydantic's
    errors()["input"] does carry the offending value while the sanitizer never reads "input", "ctx",
    or calls str(exc)/repr(exc). Zero leaks found across all 64 checks.
    Deterministic test reproduction on the test host (isolated worktree + throwaway Postgres DB, no
    local Postgres available on the validating workstation): 263 passed, 0 failed, 0 skipped, across
    the adapter (77, including the candidate's 12 new TestValidationErrorSafeDiagnostics cases run
    individually), service-contract (18), retry-authority (25), budget-reservation (40),
    config/egress (37), M3.1 reasoning-contract/store (51), and bounds-and-compatibility (15) suites.
    ruff and black clean on both changed files. mypy clean on the changed implementation file; four
    pre-existing union-attr findings in shared/sdk/agent_team/store.py (0-line diff vs base, unrelated
    path) independently reproduced identically against canonical main and classified PRE_EXISTING /
    NON_BLOCKING.
    Secret-scan critical finding at scripts/verify_step66c4_be3_ra1d_missing_config_json.py:129
    independently reconfirmed as registered pre-existing baseline debt -- 0-line diff for that file
    between base and candidate -- PRE_EXISTING / NON_BLOCKING, file untouched by candidate. Zero
    findings in either changed file.
    Zero real Anthropic calls, zero diagnostic calls, live gate false throughout, budget policy
    untouched by validation activity, production count 0.

Validation quota                1 of 2 CONSUMED
Validation Round 2               NOT REQUIRED
```

## 4. Accepted technical state

```text
_parse() ValidationError branch   now appends " [<diagnostic>]" where <diagnostic> is bounded,
                                       schema-only, never a value
failure_category                  unchanged: malformed_output (non-retryable, unchanged)
Success path                      unchanged; valid CritiqueArtifact/ProposalArtifact/
                                       DecisionSummaryArtifact/PlanDraftArtifact parse identically
Downstream sanitizer               shared/sdk/agent_reasoning/models.py::sanitize_failure_reason
                                       (500-char bound, marker scan) unchanged, still applied at
                                       persistence time in service.py, independently confirmed intact
Reasoning provider                 anthropic
Reasoning model                    claude-sonnet-5
reasoning_live_enabled             false
Real Anthropic calls (this record)         0
Diagnostic Anthropic calls (this record)   0
production_executed_true_count             0
```

## 5. What accepting this remediation does NOT mean

```text
Does NOT mean the critique failure from the AT-D39 execution has been retried or resolved -- no new
   Anthropic call of any kind was made by this record or its validation
Does NOT mean AT-M3.6B.2 Live Validation's critique leg is PASS -- it stays
   CRITIQUE_REVALIDATION_PENDING
Does NOT release, settle, or alter the retained US$0.016086 reservation, or recompute the US$0.060134
   effective validation cost -- both remain exactly as recorded by AT-D39/AT-D40
Does NOT reopen or rerun propose, replay, decompose_plan, or summarize_decision -- their AT-D39
   PASS results stand unchanged and unreopened
Does NOT reactivate the AT-D33/AT-D35 budget policy -- it remains inactive
Does NOT mean the deployed test-runtime image contains this change -- it does not; see section 8
Does NOT authorize a CritiqueArtifact (or any artifact) schema change, a critique prompt change, or a
   structured-output migration -- all remain out of scope, per AT-D40
Does NOT authorize AT-M3.5, AT-M4, HumanApproval mutation, or production action
```

## 6. Merge authorization

```text
Method              git merge --ff-only
Result              main advanced 6cf72e9 -> 767c5b1, no merge commit, no rebase, no squash, no
                        cherry-pick, no force push, no candidate alteration
Reconciliation      docs/governance only -- this record, AI_AGENTS_PM_STATE.md, source/progress.md,
                        committed separately on top of the fast-forwarded tip
Guarded trees       apps/ shared/ agents/ migrations/ infra/ scripts/ tests/ MUST be byte-identical
                        between implementation_end (767c5b1) and the reconciliation tip
```

`AT_M3_6B_2_CRITIQUE_VALIDATIONERROR_SAFE_DIAGNOSTICS_IMPLEMENTATION_END` names `767c5b1`, the exact
independently validated commit, and does not follow past it. The reconciliation commit that lands on
top is documentation and never carried validation coverage.

## 7. What this decision does NOT do

```text
Does NOT authorize a critique-only Live Validation execution, or any part of it
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
Does NOT amend AT-D32, AT-D33, AT-D34, AT-D35, AT-D36, AT-D37, AT-D38, AT-D39 or AT-D40
Does NOT claim the runtime or the product is production-ready in any respect
```

## 8. Next decision

`AT-M3.6B.2 Critique Safe Diagnostic Runtime Image Redeploy` — the deployed test-runtime image must
be rebuilt from this new canonical `main` (containing `767c5b1`) before any further critique-only Live
Validation attempt; the currently running image predates this candidate and does not contain the
diagnostic-capture fix. After that redeploy, a **fresh**, critique-only, bounded Live Validation
authorization (policy activation -> one critique call -> terminal policy deactivation) is still
required before any real Anthropic request is attempted again. Nothing in this record supplies it.
AT-D32's envelope stays 5 of 12 consumed, 7 remaining.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
