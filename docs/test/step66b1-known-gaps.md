# Step 66B.1 — Known Gaps

> **Documentation only. No production action.**

## Blocking (none)

No blocking gaps — 66B.1 PASS criteria met (see completion report).

## Non-blocking

1. **No real identity/session model.** RBAC uses a fail-closed test-only header simulation
   (`TASK_API_TEST_AUTH_ENABLED` + `X-Task-Actor`/`X-Task-Role`), not the operator-actions
   session+CSRF machinery (`shared/sdk/operator_actions/*`). Deferred to whichever stage wires the
   Admin Console UI to real login (likely when 66B.2 needs a browser session).
2. **No CSRF protection.** Because there is no cookie-based session yet, CSRF is not applicable in
   66B.1; it will be needed once 66B.2 adds a browser-session auth path.
3. **`canceled` state has no endpoint.** The full lifecycle enum includes `canceled`, but no
   `POST /tasks/{id}/cancel` was implemented (not in the 66B.1 required-endpoints list). Deferred.
4. **No update endpoint.** `task.updated` audit event is defined in the platform pattern but no
   `PATCH /tasks/{id}` exists yet (not in the 66B.1 required-endpoints list). Deferred.
5. **`project_id` has no FK constraint.** Stored as a nullable UUID without a foreign key to any
   projects table, to avoid coupling risk with the multi-project schema's exact shape. Deferred
   validation to the application layer if/when needed.
6. **Non-first-class task types are recorded but not routed.** `intake_planning_only=true` is set
   correctly, but there is no actual intake/planning/documentation flow endpoint to route them to
   yet (per D6/D14 — future stage).

## Deferred to 66B.2

Admin Console Task Assignment UI (`/tasks`, `/tasks/new`, `/tasks/{id}` pages) consuming this API;
real browser-session auth if needed for the UI.

## Deferred to later stages

Agent Workroom (66C), Delivery Inbox (66D), fixed-team dispatch wiring (66E), multi-channel intake
(66F), notifications + Action Center (66G).

## Statement

No production action occurred. No workflow dispatch occurred. No external action occurred. Gaps
above are all non-blocking for the 66B.1 PASS criteria.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
