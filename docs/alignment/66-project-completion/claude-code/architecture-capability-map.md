# Architecture Capability Map — Step 66ALIGN.1-CC

> **Analysis and documentation only. No implementation, merge, deployment, or runtime modification
> performed by this document.**

## 1. What exists today (real, running, not fabricated)

```text
Orchestrator (FastAPI, apps/orchestrator/src/): central API surface -- /health, /operations/*
  read endpoints, Task API (/tasks, /tasks/{id}, /tasks/{id}/workroom), Admin Console static mount.
Task API + RBAC scoping: shared/sdk/tasks/rbac.py TASK_ROLES frozenset (requester,
  pm_engineering_lead, reviewer_approver, platform_admin, agent_operator,
  security_compliance_reviewer); server-side requester-scoping enforced in task_api.py. Test-only
  X-Task-Actor/X-Task-Role header auth, gated by TASK_API_TEST_AUTH_ENABLED (fail-closed).
5-agent pipeline (intake, requirement, project-planner, development, devops, qa, workspace-operator,
  design-review, mini-delivery-pilot, delivery-package -- 10 agent services total per docker compose
  ps): each a FastAPI service, healthy in test.
Approval engine, policy engine, audit service + audit worker, communication gateway, discord
  gateway, github automation, notification worker, retry scheduler: all running, healthy, in test.
Postgres 16 (trust auth, test-only), Redis 7 (Streams + consumer groups for the agent pipeline),
  Vault (dev mode, ephemeral -- test-only), Prometheus/Grafana/Alertmanager/Tempo observability
  stack.
Admin Console (apps/admin-console/, React 18 + Vite + TypeScript strict): Overview
  (attention-first), Tasks (list + detail + workroom + query-param deep links), Safety Center +
  calm safety posture (FE.1B/FE.1B.1), Audit Evidence, Agent Executions, ~19 Platform Ops
  diagnostic/evidence pages, Navigation Polish (FE.1D-S1: subtitles, Soon/Read-only/Evidence
  badges, compact density).
CI-adjacent tooling: black/ruff/mypy for Python, ESLint absent (documented gap, non-blocking),
  Vitest + React Testing Library for frontend, per-stage Python verifier scripts + pytest wrappers
  (the project's own governance mechanism, not a generic CI pipeline).
```

## 2. What is designed/decided but not yet implemented

```text
Team RBAC (6-role matrix, Q1 locked in the 66A.3 blueprint): rbac-blueprint.md exists;
  Settings/Roles & Permissions UI does not.
Clarification timeout model (Q2: 24h reminder / 72h blocked-expired): decided; Step 66C.4
  (Reminder/Expiry scheduler) not built.
Delivery Inbox + 6-action acceptance gate (Accept/Reject/Request-Changes/Re-run-QA/
  Escalate/Archive): blueprinted (delivery-inbox-blueprint.md); Step 66D not built.
Operator Action Center (9 queues incl. Approvals P0, DLQ/Retry P0): blueprinted
  (operator-action-center-blueprint.md); Step 66D/66G not built.
Multi-channel intake (Slack, Telegram gateways; Discord notify-first already exists):
  multi-channel-intake.md exists as a discovery doc; Step 66F not built.
Governed web research (whitelist v0.1, 10 sources, connector not implemented): explicitly flagged
  as a missing capability at discovery time (66A.1) and still missing.
FE.1D Slice 2 (microcopy/field-label cleanup): boundary + slicing plan exist
  (docs/contracts/66ui4-fe1d-navigation-microcopy/); not authorized, not implemented.
```

## 3. What is explicitly out of scope / deferred by design

```text
Real production Kubernetes/Helm/ArgoCD substrate (only a non-production "kind" cluster + non-
  production ArgoCD instance exists, used exclusively for dry-run governance-gate rehearsal).
Real production secret store (Vault dev-mode only).
Real backup/DR remediation (encryption_no_key, storage_not_off_host, schedule_dry_run_only,
  migration_down_gaps all remain open by design -- never scheduled for remediation in any completed
  stage to date).
Any real production deployment, production data, or production external action -- every stage in
  this project's history enforces production_executed_true_count=0 and this has held without
  exception.
```

## 4. Architecture layering (as-built, not aspirational)

```text
Layer 1 -- Data/messaging: Postgres (relational state), Redis Streams (agent-pipeline event bus).
Layer 2 -- Agent services: 10 FastAPI microservices implementing the actual pipeline stages
  (intake -> requirement -> planning -> development/devops/qa -> delivery-package -> mini-delivery-
  pilot), each independently deployable, already containerized.
Layer 3 -- Platform services: approval-engine, policy-engine, audit-service/worker, communication-
  gateway, discord-gateway, github-automation, notification-worker, retry-scheduler -- the
  governance/safety/integration backbone.
Layer 4 -- Orchestrator: the single FastAPI app that exposes /operations/*, the Task API, and
  mounts the Admin Console static bundle. This is also the SPA's only server-side integration
  point today (no separate BFF/gateway layer).
Layer 5 -- Admin Console frontend: React SPA, read-mostly (GET-only API client with an explicit
  SUPPORTED_METHODS=["GET"] guard from Stage 50, since extended narrowly for Task API writes under
  RBAC scoping), served by StaticFiles(html=True) with no SPA-fallback route (the known deep-link
  gap).
```

This layering is coherent and was not improvised piecemeal — the agent pipeline, approval/policy/
audit backbone, and Task API all predate the current FE.1A–FE.1D Admin Console polish track, and
the polish track has consistently been scoped to the frontend layer only, never touching layers
1–4. This is a structural strength for the milestones ahead: M1–M3 do not require re-architecting
anything already running, only adding new UI surfaces and a small number of new endpoints/fields
against the existing Task API and agent-pipeline event model.

## Statement

Analysis and documentation only. No implementation, merge, deployment, or runtime modification
performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
