# Mini Project Delivery Path — Roadmap

This is the roadmap from the project-planning foundation to an end-to-end mini
project delivery pilot. Each step builds on the previous one.

| Step | Title | Status | What it adds |
|---|---|---|---|
| 43 | Project Planner & Task Graph | **closed** | brief, user stories, acceptance criteria, milestones, work-item graph, dependency validation, planning-only orchestration + operations visibility |
| 44 | Agent Discussion & Design Review Protocol | **closed** | structured multi-role discussion + design review + gates + go/no-go on a project graph, review-only, before any code |
| 45 | Real Repo Workspace Operator v1 | **closed** | a controlled, allowlisted workspace operator that generates a FastAPI Todo project, runs pytest + static checks, and produces diff / artifacts / work-item execution links — no repo write, no PR, no deploy, no real LLM |
| 46 | Mini Project Delivery Pilot | **closed** | chains plan → design review → controlled workspace → test/static evidence → acceptance evaluation → QA summary → safety summary → mini delivery pilot report, controlled-only |
| 47 | Delivery Package & Acceptance Gate | **done (this stage)** | assemble a formal delivery package (14 sections + artifacts), gate it (18 acceptance checks), produce handoff summaries + readiness snapshot + operator-review placeholder; `ready_for_operator_review`, human acceptance pending, controlled-only |
| 48 | Admin Console v0 (read-only) | planned | read-only operator visibility over projects / reviews / workspaces / pilots / delivery packages |
| 49 | Backup / DR Gap Closure | planned | close the documented backup / DR readiness gaps before production delivery |
| 50 | Admin Console v1 (operator actions) | planned | enable real operator accept / reject / request-changes with policy + approval + audit |

## Current foundation (Steps 43–44)

* Projects, briefs, user stories, acceptance criteria, milestones, work items,
  dependencies, risks, artifacts, graph snapshots (Step 43).
* Deterministic FastAPI Todo template + dependency graph validation (Step 43).
* Planning-only orchestration: project-scale requests route to the
  project-planner-agent; the workflow stops at `project_planned` (Step 43).
* Multi-role design review: discussion sessions, deterministic role
  contributions (no chain-of-thought), six reviewers, acceptance coverage,
  seven review gates, and a go/no-go decision; review-only — the workflow stops
  at `design_reviewed` / `design_reviewed_with_findings` / `design_review_blocked`
  (Step 44).
* Operations API for project / work item / dependency / graph / acceptance /
  delivery-readiness + discussion / design-review / findings / gates /
  go-no-go / acceptance-coverage visibility.
* Controlled workspace operator: after a non-blocked design review, the
  orchestrator requests a controlled workspace execution that generates a
  deterministic FastAPI Todo project under an allowlisted root, runs pytest +
  static checks, and records diff / artifacts / work-item execution links;
  controlled-only — the workflow stops at `workspace_tests_passed` /
  `workspace_tests_failed` / `workspace_execution_failed` and never deploys or
  opens a PR (Step 45).
* Mini project delivery pilot: one controlled run chains plan → design review →
  workspace execution → test/static evidence → evidence-based acceptance
  evaluation → QA summary → safety summary → a mini delivery pilot report, with
  pilot-level steps, evidence, and artifact links; controlled-only — no PR, no
  deploy, no real LLM, `production_executed=false` (Step 46).
* Delivery package & acceptance gate: a completed mini pilot is assembled into a
  formal delivery package (14 sections, linked artifacts, acceptance checklist),
  evaluated by an 18-check acceptance gate, and accompanied by business /
  technical / operator handoff summaries plus a delivery readiness snapshot and a
  pending operator-review placeholder. The gate resolves to
  `ready_for_operator_review`; human acceptance stays `pending` and operator
  action endpoints are disabled by default; controlled-only — no PR, no deploy,
  no real LLM, no external delivery, `production_executed=false` (Step 47).

## Still out of scope (carry-forward)

* Admin Console v0 read-only visibility (Step 48); backup / DR gap closure
  (Step 49); Admin Console v1 operator actions (Step 50).
* Work-item dispatch to a real implementing agent.
* Real LLM, real GitHub production write, real deploy, real escalation.
* Backup / DR readiness gaps, Kubernetes / Helm / ArgoCD baseline, real
  production secret store, real off-host backup, real pager.
