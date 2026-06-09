# Stage 30 — LLM Prompt Contract

The deterministic envelope every LLM provider receives. The producer
hashes the prompt + response before persistence and stores only a
redacted, length-bounded preview.

## Envelope

```json
{
  "contract_version": "1.0",
  "task_id": "<task-id>",
  "execution_mode": "delivery_task | scrum_project | simple_task",
  "request_type": "dev.api | dev.test | …",
  "interaction_type": "development_plan | patch_proposal | test_plan",
  "task_summary": "<first 2000 chars of the task description>",
  "acceptance_criteria": ["<criterion 1>", "…"],
  "allowed_paths": ["docs/generated/", "apps/demo-generated/", …],
  "denied_paths": ["infra/*", "migrations/*", "*secret*", …],
  "safety_rails": {
    "production_executed": false,
    "no_secrets": true,
    "no_delete": true,
    "no_production_deploy": true,
    "no_branch_protection_modification": true,
    "no_destructive_commands": true,
    "no_real_github_write": true,
    "must_ask_clarification_if_uncertain": true,
    "must_mark_requires_human_review_true": true
  },
  "output_schema": "LLMDevelopmentPlan | LLMPatchProposal | LLMTestPlan",
  "instructions": "Return JSON that matches the requested schema. …"
}
```

## Hash & preview

* `prompt_hash = sha256(prompt_json)`
* `prompt_preview = redact_text(prompt_json)` — token / key / private
  key patterns are replaced with `[REDACTED:<name>]` markers, then
  the result is truncated to 240 chars with a `…[truncated]` suffix.
* `response_hash = sha256(response_json)`
* `response_preview = redact_text(response_json)`

The full prompt and response are **never** written to disk, the
audit log, or notifications. Only the hash + redacted preview enter
`llm_interactions`.

**Stage 35 update:** the `RealLLMPlanOnlyProvider` runs every wire
response chunk through the same `redact_text` helper BEFORE the
parsed plan's `summary`, `proposed_steps`, `assumptions`, `questions`,
`risks`, and `test_strategy` fields are populated. Token-shaped
strings in the model's reply never reach the operator-visible
preview. The provider also adds the response hash (first 16 hex
chars only) to the plan's `assumptions` list so an operator can
correlate the recorded interaction with the wire response without
storing the body.

## Schema-invalid handling

If the LLM returns JSON that does not match the requested schema —
missing fields, wrong types, embedded `delete` change_type, or any
secret-shaped literal — the proposal is marked
`status=blocked` with a `schema_invalid` violation, the workflow
moves to `blocked_for_human_review`, and an `llm_proposal_blocked`
audit event is emitted.

## Where this lives in code

* `shared/sdk/llm/prompt_contract.py` — `build_prompt_contract`,
  `hash_text`, `redact_text`.
* `shared/sdk/llm/policy.py` — `apply_llm_safety_policy`,
  `LLMSafetyPolicy`.
* `agents/development-agent/src/llm_planner.py` — uses both above.

## Trip-words for verify scripts

The mock provider deliberately fails the policy when the description
contains one of these markers, so verify scripts can exercise the
block path without writing any real credentials:

* `denied` → denied-path proposal (lands on `infra/...`)
* `deletion` → `change_type=delete`
* `secret-token` → a synthetic-but-token-shaped literal
* `destructive` → `rm -rf` in proposed content

These trip-words exist only to feed the safety policy a known-bad
sample. They are inert in production paths.
