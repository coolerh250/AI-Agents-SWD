# Application Security Asset Inventory (Step 54.1)

Source of truth: [infra/security/application-security-asset-inventory.yaml](../../infra/security/application-security-asset-inventory.yaml).

Inventories every first-party component and its security-relevant surface (language,
runtime, package files, Dockerfiles, deployment targets, and whether it handles
secrets / user input / auth / network / persistence), with the scans each requires and any
blockers. It reflects the **actual** repo state.

## Coverage

26 assets: 11 apps (orchestrator, policy-engine, approval-engine, audit-service,
audit-worker, communication-gateway, discord-gateway, github-automation, notification-worker,
retry-scheduler, admin-console), 12 agents (intake, requirement, development, qa, devops,
project-planner, design-review, workspace-operator, mini-delivery-pilot, delivery-package,
plus backend/frontend scaffolds), the shared SDK, the Kubernetes/Helm/GitOps manifests, and
the migration/backup/restore jobs. 24 are production-relevant; the two `.gitkeep`-only agent
scaffolds (backend-agent, frontend-agent) are marked not production-relevant.

## Notable blockers per asset

- All Python services/agents: `dockerfile_no_nonroot_user`, `python_dependencies_unpinned`.
- Kubernetes/Helm/GitOps: `image_digest_not_pinned`, `no_cluster_runtime_smoke`.
- Jobs: `pg_dump_psql_runtime_smoke_required`, `image_digest_not_pinned`.

Verified by `scripts/verify_security_asset_inventory.py`
(`SECURITY_ASSET_INVENTORY_VERIFY`).
