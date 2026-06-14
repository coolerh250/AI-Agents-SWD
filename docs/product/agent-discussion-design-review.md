# Agent Discussion & Design Review Protocol (Stage 46)

Builds on the Stage 45 project planner / task graph. Given an already-planned
project graph, the platform produces a structured, governable, auditable,
repeatable multi-role design review and a go/no-go decision — **before** any
code is written.

It is **review-only / planning-only**: no real LLM, no repo write, no PR, no
deploy, no work-item dispatch, no real external messaging. `production_executed`
is always `false`.

## Purpose

A single design review aggregates these role reviews into findings, gates, and a
decision:

* Requirement review · Scope / non-scope validation
* Architecture review · Data model / API design review
* Development implementation strategy
* QA strategy review · Security risk review
* DevOps / delivery readiness review
* Acceptance criteria coverage review · Risk register review
* Go / No-Go design decision summary

## Discussion session model

`agent_discussion_sessions` holds one structured discussion per project/decision
(`session_type`, `status`, `review_mode=deterministic_template`,
`planning_only=true`). `agent_discussion_participants` records the role
participants (review-output sources, not real LLM conversants).
`agent_discussion_contributions` holds each role's output **summary** only.

## Participant model

Full pre-execution review participants: requirement-agent, project-planner-agent,
architecture-capability, development-agent, qa-agent, security-capability,
devops-agent, delivery-capability (approver). Future-capability roles are
review sources only and never dispatch work.

## Contribution rules — no chain-of-thought

A contribution stores `summary`, optional `rationale_summary` (a short
conclusion), `confidence`, `severity`, and artifact refs. There is **no**
chain-of-thought, **no** raw prompt, and **no** transcript table — enforced by
the migration (no such columns) and by `shared/sdk/agent_discussion/safety.py`.

## Deterministic template mode

`contribution_templates.py` produces a fixed set of role contributions from the
project brief / work items / acceptance criteria / risks. No LLM is called. A
future real-LLM mode is gated off by `ENABLE_DESIGN_REVIEW_REAL_LLM=false`.

## Design review flow

1. Load the project context (brief, stories, work items, dependencies,
   acceptance criteria, risks, graph validation status).
2. Create a discussion session + participants + deterministic contributions.
3. Run the six reviewers + acceptance-coverage → findings.
4. Evaluate gates (`gate_evaluator`) and derive a go/no-go decision.
5. Persist findings, decisions, gates, and a redacted design-review-summary
   artifact.
6. Emit audit + notification events + metrics; report the decision to the
   orchestrator (`design_review.completed` / `design_review.blocked`).

## FastAPI Todo review example

For the Stage 45 `fastapi_todo_service` graph the review yields: 8 participants,
10 contributions, 7 gates, no critical findings, 0 blocking findings, and a
`planning_only` decision (review-only). Gates: requirement/architecture/
implementation/qa/delivery `passed`; security + pre-execution
`passed_with_findings`. See [design-review-gates.md](design-review-gates.md).

## Limitations / safety constraints

* No real LLM, no repo write, no PR, no deploy, no work-item dispatch.
* `discussion.*` and `design_review.*` notification events are on the default
  real-delivery denylist (`project.*`, `audit.*`, `verification.*` remain
  denied too).
* Audit rows carry only decisions / artifact refs / summaries — never
  chain-of-thought, never secrets.
* An invalid project graph produces a `no_go` (blocked) review; a critical
  finding also produces `no_go`. Neither dispatches anything.
