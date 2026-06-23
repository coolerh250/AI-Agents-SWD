# Dependency Surface Inventory (Step 54.1)

Source of truth: [infra/security/dependency-surface-inventory.yaml](../../infra/security/dependency-surface-inventory.yaml).

A **surface** inventory + scan-requirement mapping only — no CVE judgement, no scan
execution. Unknown sources are marked `unknown`, never assumed safe.

## Contents

- **Python:** runtime deps (fastapi, uvicorn, pydantic, redis, httpx, asyncpg, langgraph,
  prometheus_client, opentelemetry-*, PyYAML, jsonschema), dev/test deps (pytest,
  pytest-asyncio, ruff, black, mypy), security-critical subset. `lockfileMissing: true`.
- **Node:** react / react-dom / react-router-dom + vite/typescript/vitest/eslint dev deps.
  `lockfileMissing: false` (package-lock.json).
- **Docker base images:** `python:3.12-slim` (all services), `node` (admin-console build).
- **Helm/compose third-party images:** postgres:16, redis:7, hashicorp/vault:1.17,
  prom/prometheus, prom/alertmanager, grafana/grafana, grafana/tempo — none digest-pinned.
- **System packages:** postgresql-client (psql / pg_dump / pg_restore) in the job images.
- **GitHub Actions:** none present; CI scan integration deferred to Step 54.2+.

Unknowns recorded: Python/Node transitive trees (no resolver run), node build image digest.

Covered by `tests/test_dependency_surface_inventory.py`.
