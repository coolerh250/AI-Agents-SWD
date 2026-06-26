# Multi-project Delivery & Work-item Dispatch — Verification (Step 57)

## Combined
```bash
PYTHON=.venv/bin/python ORCHESTRATOR_URL=http://localhost:8000 \
  ./scripts/verify_multi_project_delivery_dispatch_baseline.sh
```
Final marker: `MULTI_PROJECT_DELIVERY_DISPATCH_BASELINE_VERIFY: PASS | BLOCKED | FAIL`.
Runs the Step 56 combined (chains Step 51–56), the 10 Step 57 verifiers, the targeted
tests, and the safety posture check.

## Individual verifiers + markers
`MULTI_PROJECT_SCHEMA_VERIFY`, `WORK_ITEM_LIFECYCLE_VERIFY`,
`WORK_ITEM_DISPATCH_POLICY_VERIFY`, `WORK_ITEM_DISPATCH_RUNTIME_VERIFY` (live API),
`PROJECT_DELIVERY_STATE_VERIFY`, `DELIVERY_PACKAGE_PROJECT_LINKAGE_VERIFY`,
`PROJECT_WORK_ITEM_AUDIT_MAPPING_VERIFY`, `MULTI_PROJECT_OPERATIONS_VISIBILITY_VERIFY`,
`ADMIN_CONSOLE_MULTI_PROJECT_VERIFY`, `MULTI_PROJECT_SAFETY_FIELDS_VERIFY` (live).

## Read endpoints
`GET /operations/delivery/{projects, projects/{id}, projects/{id}/work-items,
work-items/{id}, work-items/{id}/events, work-items/{id}/dispatches,
projects/{id}/delivery-state}`. Writes: `POST /operations/delivery/projects`,
`.../projects/{id}/work-items`, `.../work-items/{id}/dispatch` (auth + CSRF + reason +
audit). Mock intake: `POST /intake/mock/project-work-item` (communication-gateway).
