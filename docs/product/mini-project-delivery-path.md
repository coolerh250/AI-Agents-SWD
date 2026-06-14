# Mini Project Delivery Path — Roadmap

This is the roadmap from the project-planning foundation to an end-to-end mini
project delivery pilot. Each step builds on the previous one.

| Step | Title | Status | What it adds |
|---|---|---|---|
| 43 | Project Planner & Task Graph | **done (this stage)** | brief, user stories, acceptance criteria, milestones, work-item graph, dependency validation, planning-only orchestration + operations visibility |
| 44 | Agent Discussion & Design Review Protocol | planned | structured multi-agent discussion + design review on a project graph before any code |
| 45 | Real Repo Workspace Operator v1 | planned | a controlled, sandboxed workspace operator that can materialise work-item outputs into files (still human-reviewed, no production write) |
| 46 | Mini Project Delivery Pilot | planned | drive a small project (FastAPI Todo) end-to-end through the graph in dev/test only |
| 47 | Delivery Package & Acceptance Gate | planned | assemble a delivery package and gate it on the acceptance criteria before it is considered delivery-ready |

## Current foundation (Step 43)

* Projects, briefs, user stories, acceptance criteria, milestones, work items,
  dependencies, risks, artifacts, graph snapshots.
* Deterministic FastAPI Todo template.
* Dependency graph validation (cycle / self / duplicate / missing node).
* Planning-only orchestration: project-scale requests route to the
  project-planner-agent; the workflow stops at `project_planned`.
* Operations API for project / work item / dependency / graph / acceptance /
  delivery-readiness visibility.

## Still out of scope (carry-forward)

* Real repo workspace operator (Step 45).
* Mini project delivery pilot (Step 46).
* Work-item dispatch to a real implementing agent.
* Real LLM, real GitHub production write, real deploy, real escalation.
* Backup / DR readiness gaps, Kubernetes / Helm / ArgoCD baseline, real
  production secret store, real off-host backup, real pager.
