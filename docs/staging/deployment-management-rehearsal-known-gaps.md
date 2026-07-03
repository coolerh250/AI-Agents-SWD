# Deployment Management Rehearsal — Known Gaps (Step 64F.2)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Gaps observed during the orchestrator-only restart rehearsal. No rebuild or data change.**

## Gaps observed
1. **SPA deep-link hard-refresh 404.** `/admin/agent-executions` (and other deep routes)
   hard-refresh 404 after the restart; `/admin/` serves 200. Unchanged from prior stages —
   structural (no StaticFiles catch-all). **Operator impact:** none if navigating via top-nav tabs.
   **Follow-up:** optional catch-all serving `dist/index.html` for `/admin/*` in a future test/QA
   change.

## Non-gaps confirmed by the rehearsal
- Orchestrator recovers to healthy after an isolated restart; the other 21 services are unaffected.
- No data loss — all formal-evidence endpoint counts identical before/after.
- Bundle hash unchanged (restart does not rebuild).
- Safety posture unchanged (`production_executed_true_count=0`; external integrations off).

## Operator impact summary
No blocking operator impact. The deep-link 404 is an accepted non-blocking gap; all required
evidence is reachable through normal tab navigation.

## Posture
Orchestrator-only restart rehearsal. No rebuild, no full-stack restart, no teardown, no restore, no
workflow re-run, no production action; `production_executed_true_count` remained 0.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
