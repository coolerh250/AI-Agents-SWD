# Release Governance — Runtime (Step 60)

- SDK: `shared/sdk/release_governance/` (candidates / deployment_intent / evidence /
  readiness / rollback / audit / store)
- API: `apps/orchestrator/src/release_governance_api.py`
- Migration: `migrations/026_release_deployment_governance.sql`
- Verifier: `scripts/verify_release_governance_runtime.py` → `RELEASE_GOVERNANCE_RUNTIME_VERIFY`

## Flow
1. Operator authenticates (test-local auth + CSRF) and POSTs a release candidate with a
   `reason`, `version_label`, optional `project_id` / linkage, and a non-production
   `target_environment` (defaults to `nonprod`; production is rejected).
2. The candidate is persisted to `release_candidates` and an audit event is written.
3. The operator POSTs a deployment intent for the candidate with a `requested_action`
   (`validate_only` / `prepare_nonproduction` / `request_operator_review`). The intent is
   classified — never executed: a production target or forbidden action is **blocked**.
4. Evidence (`/evidence`) and readiness (`/readiness`) are derived read-only; missing
   evidence and any production target block readiness. `production_ready` is always false.

## Endpoints
- `POST /operations/release/candidates` — controlled (auth + CSRF + reason + audit).
- `POST /operations/release/candidates/{candidate_id}/deployment-intents` — controlled.
- `GET  /operations/release/{overview,policy,safety,limitations,readiness-summary}`.
- `GET  /operations/release/candidates[/{id}[/evidence|/readiness]]`.
- `GET  /operations/release/deployment-intents[/{id}]`.

There is **no** deploy / ArgoCD sync / merge / image-push / production-approval endpoint.
A deployment intent never executes a deployment; no token is ever returned.

## Storage
`release_candidates`, `deployment_intents`, `release_evidence_packages`,
`release_readiness_decisions`, `release_audit_events` — `target_environment` can never be
production (CHECK); `production_ready` / `production_executed` default false.
