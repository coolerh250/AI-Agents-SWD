# Staging Deployment Management — Operator Checklist (Step 64F.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Checklist design only — no action executed by this document. Destructive steps require separate explicit authorization.**

Operator-facing checklists for common staging deployment tasks. Each maps to the full procedure in
[deployment-management-sop.md](deployment-management-sop.md) and commands in
[deployment-management-command-reference.md](deployment-management-command-reference.md).

## Orchestrator redeploy (standard)
- [ ] Repo `git status` clean; `git pull --ff-only origin main`; record HEAD.
- [ ] `docker compose … build orchestrator`.
- [ ] `docker compose … up -d orchestrator`.
- [ ] `/health` 200; `/admin/` 200 (record bundle hash); `/operations/safety`
      `production_executed_true_count=0`.
- [ ] Formal pages validated (`/delivery`, `/agent-executions`, `/task-graph`, `/qa-code`,
      `/audit-evidence`, `/safety`) via top-nav tabs.
- [ ] Record outcome; notify operator.

## Start / stop / restart
- [ ] Start: `bash scripts/start_staging_runtime.sh`; then `bash scripts/check_staging_runtime.sh`.
- [ ] Orchestrator restart: `docker compose … restart orchestrator`; re-check health.
- [ ] Full-stack stop (keep volumes): `bash scripts/stop_staging_runtime.sh`.
- [ ] Confirm **no** `down -v` unless a destructive teardown is separately authorized.

## Upgrade
- [ ] Pre-upgrade evidence captured (HEAD, bundle hash, health, safety).
- [ ] Change passed the test/QA gate before redeploy.
- [ ] Redeploy (orchestrator-only) + post-upgrade validation.
- [ ] Operator re-review triggered if operator-visible behavior changed.
- [ ] Rollback decision recorded if validation failed.

## Rollback (explicit authorization)
- [ ] Previous known-good commit identified.
- [ ] `git checkout <good>` → rebuild + recreate orchestrator.
- [ ] Post-rollback validation PASS; `production_executed_true_count=0`.
- [ ] From/to commits + reason recorded; operator notified.

## Teardown / restore (separate explicit authorization)
- [ ] Confirm authorization type (volume-preserving vs destructive).
- [ ] Destructive teardown (`--volumes`) only with explicit sign-off + recorded reason.
- [ ] Restore: validated backup + data-integrity checks + operator sign-off before use.

## Safety gate (every task)
- [ ] `production_executed_true_count=0`.
- [ ] Live GitHub/Discord/LLM disabled/mocked (unless a controlled phase is separately authorized).
- [ ] No secrets printed; `.env.staging.local` never displayed.
- [ ] Acceptance based on formal product UI, not the Demo Evidence / Diagnostics page.

## Status
Step 64E: **PASS**. Step 64F: **SOP_DESIGN_COMPLETED**. Staging deployment management only, not
production readiness. No runtime change in this stage; no production action;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
