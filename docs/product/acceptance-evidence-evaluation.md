# Acceptance Evidence Evaluation (Stage 48)

The mini delivery pilot evaluates each `project_acceptance_criteria` row
against concrete workspace evidence and records an `acceptance_evaluations`
row.

## Criteria mapping model

Each criterion is classified (by `criterion_key` for the FastAPI Todo
template, else by description / verification_method keywords) into one of:

* **test** — needs a passing `pytest` run.
* **doc** — needs a generated documentation file (e.g. `README.md`).
* **safety** — satisfied by the controlled-only safety evidence.
* **manual** — no automated evidence → `pending` (manual review required).

## Evidence types

`test_run`, `static_check`, `generated_file`, `workspace_artifact`,
`documentation_review`, `manual_review_required`.

## satisfied / failed / pending / waived rules

* **satisfied** — concrete evidence supports the criterion (pytest passed,
  README generated, safety safe).
* **failed** — evidence contradicts it (pytest failed; a high-risk safety
  flag set).
* **pending** — evidence is genuinely unavailable (e.g. pytest skipped because
  a dependency is absent, or README not generated). Never auto-promoted to
  satisfied.
* **waived** — supported by the schema but **never auto-applied** this stage;
  waiving is an explicit operator decision.

## FastAPI Todo example

With pytest passing and `README.md` generated, all ten criteria
(AC-001..AC-010) are `satisfied` (0 failed). If pytest is skipped, the CRUD /
persistence / pytest criteria become `pending` while the README and safety
criteria remain `satisfied`. If pytest fails, AC-007 (and the CRUD criteria)
are `failed`.
