# Rebuild/Redeploy Rehearsal — Known Gaps (Step 64F.3)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Gaps observed during the orchestrator-only rebuild/redeploy rehearsal. No full-stack rebuild or data change.**

## Gaps observed
1. **SPA deep-link hard-refresh 404.** `/admin/agent-executions` (and other deep routes)
   hard-refresh 404 after the redeploy; `/admin/` serves 200. Unchanged, structural (no StaticFiles
   catch-all). **Operator impact:** none if navigating via top-nav tabs. **Follow-up:** optional
   catch-all serving `dist/index.html` for `/admin/*` in a future test/QA change.

## Non-gaps confirmed by the rehearsal
- Orchestrator-only build + `up -d` recovers the orchestrator to healthy; the other 21 services are
  unaffected.
- No data loss — all formal-evidence endpoint counts identical before/after.
- Bundle hash unchanged (the synced `44f9a40..9ec9676` diff is docs/scripts/tests only — no `apps/`
  code change), confirming the redeploy is deterministic for an unchanged app.
- Safety posture unchanged (`production_executed_true_count=0`; external integrations off).

## Operator impact summary
No blocking operator impact. The deep-link 404 is an accepted non-blocking gap; all required
evidence is reachable through normal tab navigation.

## Posture
Orchestrator-only rebuild/redeploy rehearsal. No full-stack rebuild, no full-stack restart, no down
and no down -v occurred, no teardown, no restore, no rollback, no workflow re-run, no image push, no
production action; `production_executed_true_count` remained 0.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
