# QA & Safety Evidence (Stage 48)

## QA status rules (`qa_evidence_reports`)

* **passed** — pytest passed AND static checks (compileall, and ruff when
  present) passed.
* **passed_with_findings** — pytest passed but an optional static check (ruff)
  was skipped, or pytest itself was skipped due to a genuinely unavailable
  dependency (compileall used as the offline fallback).
* **failed** — pytest failed (or a static check failed while pytest passed).
* **blocked** — no pytest run executed at all (environment issue).

`tests_total` / `tests_passed` / `tests_failed` are carried from the workspace
pytest run when available.

## Safety status rules (`safety_evidence_reports`)

* **safe** — every high-risk flag is false.
* **blocked** — any high-risk flag is true.

High-risk flags (all expected false in controlled-only mode):
`production_executed_count>0`, `github_write_performed`, `pr_created`,
`deployment_performed`, `real_llm_used`, `real_external_delivery_performed`,
`repo_root_modified`, `secret_leak_detected`, `chain_of_thought_persisted`.

The `chain_of_thought_persisted` field is a governance assertion (always
false) — it records that no chain-of-thought was persisted; it does not store
any chain-of-thought content.

## Blocked conditions

A blocked safety report fails the pilot before the report step. A failed QA
report leaves the mini delivery report in `draft` (not `ready`).

## Controlled-only constraints

The pilot never writes GitHub, creates a PR, pushes a branch, deploys, calls a
real LLM, or delivers externally. Output summaries are secret-redacted; no raw
code or chain-of-thought is persisted.
