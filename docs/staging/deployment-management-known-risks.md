# Staging Deployment Management — Known Risks (Step 64F.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Risk register (design) — no runtime change executed by this document.**

Known risks of staging deployment operations and their mitigations.

## Risks
1. **Destructive teardown data loss.** `down -v` / `--volumes` deletes the 5 staging volumes
   (postgres/prometheus/grafana/tempo/alertmanager). **Mitigation:** forbidden without separate
   explicit authorization; volume-preserving `stop`/`down` is the default; restore requires a
   validated backup.
2. **Stale bundle after redeploy.** Restarting instead of rebuilding leaves the old Admin Console
   bundle. **Mitigation:** always `build orchestrator` then `up -d orchestrator`; verify the bundle
   hash in the validation plan.
3. **Migration failure on start.** A failed migration aborts bring-up. **Mitigation:**
   `start_staging_runtime.sh` stops on error; diagnose via logs; never "fix" by deleting the DB
   volume.
4. **SPA deep-link 404.** Hard-refreshing a deep route 404s. **Mitigation:** navigate via tabs
   (accepted non-blocking gap); optional catch-all fix in a future test/QA change.
5. **Accidental external integration / production action.** Enabling live GitHub/Discord/LLM or a
   production deploy from a staging task. **Mitigation:** authorization matrix marks these
   explicit/out-of-scope; `production_executed_true_count` must stay 0; safety endpoint verified
   each validation.
6. **Secret leakage.** Printing `.env.staging.local` or logs containing secrets. **Mitigation:**
   never print the env file; share only sanitized log excerpts; secret scan in CI.
7. **Full-stack restart blast radius.** Restarting all 22 services is disruptive. **Mitigation:**
   prefer orchestrator-only; full-stack restart requires explicit authorization + documented
   reason.

## Confirmed by the Step 64F.2 / 64F.3 rehearsals
- **64F.2 (restart):** risk #2 (stale bundle) did not occur — restart kept the same bundle without
  rebuilding; risk #7 (blast radius) avoided — only the orchestrator restarted; no data loss.
- **64F.3 (rebuild/redeploy):** the orchestrator-only `build` + `up -d` path mitigated risk #2 as
  designed (build then recreate; bundle deterministic for an unchanged app); risk #7 avoided again
  (orchestrator only); no data loss; safety preserved.
- The SPA deep-link 404 (risk #4) remains an accepted non-blocking gap across both rehearsals.

## Non-goals / boundaries
- This SOP is **staging deployment management**, not production readiness and not a production
  rollout. Claude Code does not decide production readiness.
- The formal product UI is the acceptance path; the Demo Evidence / Diagnostics page is not.

## Status
Step 64E: **PASS**. Step 64F: **SOP_DESIGN_COMPLETED**. No runtime change in this stage; no
production action; no image push; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
