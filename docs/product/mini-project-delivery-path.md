# Mini Project Delivery Path — Roadmap

This is the roadmap from the project-planning foundation to an end-to-end mini
project delivery pilot. Each step builds on the previous one.

| Step | Title | Status | What it adds |
|---|---|---|---|
| 43 | Project Planner & Task Graph | **closed** | brief, user stories, acceptance criteria, milestones, work-item graph, dependency validation, planning-only orchestration + operations visibility |
| 44 | Agent Discussion & Design Review Protocol | **closed** | structured multi-role discussion + design review + gates + go/no-go on a project graph, review-only, before any code |
| 45 | Real Repo Workspace Operator v1 | **done (this stage)** | a controlled, allowlisted workspace operator that generates a FastAPI Todo project, runs pytest + static checks, and produces diff / artifacts / work-item execution links — no repo write, no PR, no deploy, no real LLM |
| 46 | Mini Project Delivery Pilot | planned | drive a small project (FastAPI Todo) end-to-end through the graph in dev/test only |
| 47 | Delivery Package & Acceptance Gate | planned | assemble a delivery package and gate it on the acceptance criteria before it is considered delivery-ready |

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

## Still out of scope (carry-forward)

* Mini project delivery pilot (Step 46).
* Work-item dispatch to a real implementing agent.
* Real LLM, real GitHub production write, real deploy, real escalation.
* Backup / DR readiness gaps, Kubernetes / Helm / ArgoCD baseline, real
  production secret store, real off-host backup, real pager.
