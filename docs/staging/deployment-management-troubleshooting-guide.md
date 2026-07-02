# Staging Deployment Management — Troubleshooting Guide (Step 64F.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Diagnostic guidance only — read-only checks (GET/HEAD/logs). Any fix that changes the runtime is a separately-authorized action.**

Symptom → likely cause → read-only diagnosis → remediation (per the authorization matrix).

## Admin Console unreachable
- **Diagnose:** `docker compose … ps` (orchestrator state); `curl -fsSI http://127.0.0.1:18000/admin`;
  check the SSH tunnel `-L 18000:127.0.0.1:18000`.
- **Remediate:** if orchestrator down/unhealthy, orchestrator restart (authorized); if tunnel
  dropped, re-open it (operator side, no runtime change).

## Stale Vite bundle (old UI after a deploy)
- **Diagnose:** `curl -fsS http://127.0.0.1:18000/admin/ | grep index-*.js` and compare the bundle
  hash to the built image; confirm `up -d orchestrator` recreated the container.
- **Remediate:** re-run the orchestrator rebuild/redeploy (§E); ensure the image was rebuilt, not
  just restarted.

## Orchestrator unhealthy
- **Diagnose:** `docker compose … ps`; `docker compose … logs --tail 200 orchestrator`;
  `/health`.
- **Remediate:** address the logged cause (config/dependency); orchestrator restart; escalate if
  it persists.

## Postgres / Redis dependency issue
- **Diagnose:** `docker compose … ps postgres redis`; `check_staging_runtime.sh`; logs.
- **Remediate:** wait for health; restart the dependency if needed (authorized). **Never** delete
  volumes to "fix" a dependency — that destroys the staging DB.

## Safety warning on `/operations/safety`
- **Diagnose:** inspect the `warnings` list. `mock_vault_provider_in_use` is expected in staging.
- **Remediate:** confirm `production_executed_true_count=0` and external flags `false`; a mock-vault
  warning is acceptable staging posture, not an incident.

## SPA deep-link 404
- **Diagnose:** `/admin/` 200 but `/admin/<route>` hard-refresh 404 (no StaticFiles catch-all).
- **Remediate:** navigate via the top-nav tabs (accepted non-blocking gap); optional future fix =
  catch-all serving `dist/index.html` for `/admin/*`.

## Missing evidence in formal pages
- **Diagnose (GET):** probe the backing endpoint — `/operations/delivery/projects` +
  `.../work-items`, `/operations/agent-executions`, `/operations/workflows`, `/operations/qa/runs`,
  `/operations/code/workspaces`, `/operations/delivery/work-items/{id}/events`, `/operations/safety`.
- **Remediate:** if an endpoint is empty, the demo data may need re-seeding (a separate authorized
  action); if an endpoint 200s but the page is blank, capture it for a UI fix in test/QA (do not
  hot-patch staging).

## Log collection
- `docker compose … logs --tail <n> <service>` (share sanitized excerpts only; **no secrets**).

## Status
Step 64E: **PASS**. Step 64F: **SOP_DESIGN_COMPLETED**. No runtime change in this stage; no
production action; `production_executed_true_count=0`. Destructive/remediation actions follow the
authorization matrix.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
