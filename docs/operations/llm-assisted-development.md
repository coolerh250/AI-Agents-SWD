# Stage 30 — LLM-Assisted Development Planning Guardrails

> Status: **deterministic-mock by default**. Stage 30 introduces an
> LLM provider abstraction, prompt contract, output schema, safety
> policy, proposal artifact lifecycle, and audit trail. It does **not**
> ship a real wire-level LLM call — every external-provider code path
> ends in `REAL_LLM_TEST_SKIPPED` until the operator opts in by
> setting `RUN_REAL_LLM_TEST=true`, `ENABLE_REAL_LLM_NETWORK_CALL=true`,
> and supplying a key. Even then, Stage 30 still refuses the network.
>
> **Stage 35 update:** the `external_openai` and `external_anthropic`
> providers ship a real wire-level plan-only call (no patch, no
> workspace write, no PR draft). Every real call must clear an
> `llm_budget_policies` cap first. See
> [`llm-cost-governance.md`](llm-cost-governance.md) and
> [`real-llm-plan-only-pilot.md`](real-llm-plan-only-pilot.md).

## Provider modes

| `LLM_PROVIDER`                       | Behaviour                                              |
| ------------------------------------ | ------------------------------------------------------ |
| `mock` *(default)*                   | Deterministic in-process generator. Stable per task.   |
| `disabled`                           | Every call raises `LLMProviderError`.                  |
| `external_openai_placeholder`        | Interface guard. Always skips the real call.           |
| `external_anthropic_placeholder`     | Interface guard. Always skips the real call.           |
| `external_openai` *(Stage 35)*       | Plan-only real call. Refuses patch / test plan. Budget gated. |
| `external_anthropic` *(Stage 35)*    | Plan-only real call. Refuses patch / test plan. Budget gated. |

Switch the provider via `LLM_PROVIDER=<name>`. Anything else falls
back to `disabled` so a misconfigured env var never silently behaves
like the mock.

## Mock-provider flow

1. The development-agent reads `ENABLE_LLM_ASSISTED_PLANNING`. If
   `false` (the default), the existing Stage 28 deterministic
   generator handles the task untouched.
2. If `true`, the agent runs the LLM planner pipeline **before** any
   deterministic write:
   - builds a deterministic prompt contract (see
     [llm-prompt-contract.md](llm-prompt-contract.md)),
   - calls `LLMProvider.generate_development_plan()`,
   - calls `LLMProvider.generate_patch_proposal()`,
   - applies `LLMSafetyPolicy` (path allowlist / denylist / no
     delete / no secret / no destructive / max files / max content
     chars / min confidence / human review),
   - persists one `llm_interactions` row per LLM call (hash + redacted
     preview only) and one `llm_proposal_artifacts` row,
   - records a zero-cost `llm_usage_records` row (the mock provider
     never spends tokens),
   - emits `llm_proposal_created` (or `llm_proposal_blocked`) audit +
     `llm.proposal_created` (or `llm.proposal_blocked`) notification.
3. If the safety policy **passes**, the deterministic Stage 28
   generator runs as before and the proposal's `linked_workspace_id`
   is set to the newly created workspace. The QA gate (Stage 29)
   still applies.
4. If the safety policy **blocks**, the deterministic generator is
   skipped entirely. A workspace row is created with
   `status=blocked` and `generator_mode=llm_assisted_proposal`; no
   files are written; the workflow moves to
   `blocked_for_human_review`.

## Real-LLM guard

A real wire-level LLM call requires every gate aligned:

* `RUN_REAL_LLM_TEST=true`
* `ENABLE_REAL_LLM_NETWORK_CALL=true`  *(Stage 30 ships this OFF)*
* A provider-specific key present: `LLM_API_KEY`, `OPENAI_API_KEY`,
  or `ANTHROPIC_API_KEY`
* The caller passed `allow_real=True`

`ExternalLLMProviderGuard` records a metric +
`llm_real_test_skipped` audit event whenever the guard refuses. The
default verify output is `REAL_LLM_TEST_SKIPPED: PASS`.

## Prompt / response redaction

* The full prompt is hashed (SHA-256) and stored as `prompt_hash`.
* `redact_text(prompt)` produces the short, redaction-safe
  `prompt_preview`. The same applies to the response.
* `[REDACTED:<name>]` markers replace any token / key / private-key
  pattern **before** the preview is truncated, so truncation can
  never leave half of a credential exposed.

## Schema validation

`LLMDevelopmentPlan`, `LLMPatchProposal`, `LLMTestPlan`, and
`LLMFileChange` enforce:

* `change_type` ∈ {`create`, `update`} — `delete` is rejected outright
* `confidence` ∈ `[0.0, 1.0]`
* `requires_human_review` is always set back to `True` even when the
  upstream response says otherwise

Schema-invalid responses produce
`{"allowed": false, "violations": [{"rule": "schema_invalid"}, …]}`.

## Policy blocks

| Rule                       | Triggered when                                                  |
| -------------------------- | --------------------------------------------------------------- |
| `path_blocked`             | A `file_path` matches the denylist or is outside the allowlist. |
| `change_type_blocked`      | Anything other than `create` / `update`.                        |
| `secret_like_content`      | Content matches a known token / key / private-key pattern.      |
| `destructive_content`      | `rm -rf`, `DROP TABLE`, `git push --force`, etc.                |
| `too_many_files`           | More than `max_files_changed` (default 5).                      |
| `content_too_large`        | More than `max_content_chars_per_file` (default 20 000).        |
| `schema_invalid`           | The output type isn't recognised or is `None`.                  |

`low_confidence:*` is a **warning** (not a violation) when
`confidence < min_confidence_for_auto_proposal` (default 0.7).

## How a proposal enters the controlled workspace

A `policy_passed` proposal is **linked** to its workspace by
`linked_workspace_id`. The deterministic Stage 28 generator continues
to be the only writer to `code_change_artifacts`. The proposal exists
as a parallel, human-reviewable artifact. The QA gate (Stage 29)
still runs against the generated workspace.

In a future stage, an operator-approved proposal can be converted to
controlled `code_change_artifacts` via
`LLMPlannerPipeline.convert_to_workspace_artifacts()`. The conversion
always re-checks every file path against the allowlist.

## How the QA gate still applies

The QA gate looks at the workspace + artifacts, not the LLM
proposal. Whether the proposal passed the LLM safety policy or not,
the QA pass / auto-fix / blocked-for-human-review decision is made by
the Stage 29 deterministic rules. The LLM safety policy is a
**pre-QA** gate; the QA rules are the **second** gate.

## Limitations

* No real LLM call by default. Provider placeholders exist for
  interface-shape testing only.
* No direct commit. Even an allowed proposal cannot be merged from
  the platform.
* Human review required on every proposal (`requires_human_review=True`).
* No real GitHub write. The dry-run path from Stage 22-28 still applies.
* No production deploy. `production_executed=false` is asserted on
  every audit row.
* Proposals do not auto-convert to code workspace artifacts in
  Stage 30 — they are advisory until an operator promotes them.
