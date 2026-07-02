# Staging Deployment Management — Authorization Matrix (Step 64F.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Design only — defines approval requirements; no action is executed by this document.**

Who may authorize which staging deployment action. "Routine" = Claude Code / operator may perform
during normal staging operations; "Operator authorization" = the operator must approve first;
"Explicit (separate) authorization" = a dedicated, recorded operator sign-off, never implied by a
prior approval.

| Action | Authorization | Notes |
|---|---|---|
| Read-only checks (`ps`, `/health`, `/admin`, `/operations/safety`, logs) | **Routine** | GET/HEAD only; no secrets printed |
| Orchestrator-only restart | **Operator authorization** | notify operator; validate after |
| Orchestrator-only rebuild/redeploy | **Operator authorization** | git ff-only + `build orchestrator` + `up -d orchestrator` + validate |
| Single non-orchestrator service restart | **Operator authorization** | document reason |
| Full-stack restart | **Explicit authorization** | document reason; broader blast radius |
| Full-stack rebuild (`build`) | **Explicit authorization** | only for dependency/base-image change |
| Rollback (to previous known-good commit) | **Explicit authorization** | orchestrator-only rebuild; no volume deletion; record from/to |
| Teardown — volume-preserving (`down`) | **Explicit authorization** | containers removed, volumes kept |
| Teardown — destructive (`down -v` / `--volumes`) | **Explicit (separate) authorization** | deletes staging DB + observability volumes |
| Restore from backup | **Explicit (separate) authorization** | + data-integrity checks + operator sign-off |
| External integration enablement (live GitHub/Slack/LLM) | **Explicit (separate) authorization** | controlled, sandbox/non-prod only; a later Step 65 phase |
| Production deploy / sync / secret | **Out of scope** | not a staging action; separate governance; Claude Code does not decide production readiness |

## Guardrails
- Destructive and production actions are **never** implied by a routine or prior approval.
- `production_executed_true_count` must remain **0** for all staging operations.
- The formal product UI is the acceptance path; the Demo Evidence / Diagnostics page is not.
- No runtime change was performed to produce this matrix; no production action; no image push.

## Status
Step 64E: **PASS**. Step 64F: **SOP_DESIGN_COMPLETED**. This is staging deployment management, not
production readiness. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
