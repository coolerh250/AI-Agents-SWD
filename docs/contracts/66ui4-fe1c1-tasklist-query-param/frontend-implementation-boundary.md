# Frontend Implementation Boundary — Step 66UI.4-FE.1C.1: TaskList Query Param Filter Support

> **Contract/boundary document only. No frontend runtime code changed by this document. No
> backend/API/database/workflow change. No new endpoint. Codex implementation not authorized by
> this document. FE.1D not authorized.**

This document defines the boundary a future Codex implementation stage (Step 66UI.4-FE.1C.1, not
yet authorized) must operate within. It does not itself authorize implementation.

## Scope: what a future implementation may do

```text
1. Parse URLSearchParams for `status` on TaskList load (e.g. via react-router-dom's
   useSearchParams(), already a project dependency -- no new package required).
2. Initialize the existing TaskList status filter (TaskListFilters.status) from that query param,
   if and only if the value is a member of TASK_STATUSES.
3. Keep the existing Status <select> control's displayed value consistent with the initialized
   filter (i.e. the dropdown visibly reflects the deep-linked status, not just the underlying
   fetch).
4. Optionally update the URL query param when the Status filter changes via the dropdown, ONLY if
   a future source-of-truth/architecture review explicitly approves two-way sync as in-scope for
   that implementation stage (see open question Q1 in the planning doc). Absent that approval,
   implement read-only-on-load only.
5. Add tests covering: a valid status query param preselects the dropdown and filters the list; an
   invalid/unrecognized status query param is ignored (falls back to "(any)", no filter applied, no
   thrown error); no query param behaves exactly as today (unfiltered).
6. Add its own docs/handoff/verifier/test artifacts under the paths this stage's own manifest
   allows.
```

## Scope: what a future implementation must not do

```text
1. No backend changes (apps/orchestrator/**, services/**).
2. No API changes -- GET /tasks?status=... already exists and already supports this exact use.
3. No database changes (migrations/**, database/**).
4. No workflow changes -- no workflow dispatch/resume introduced anywhere in this flow.
5. No new endpoint.
6. No new route -- /tasks already exists; query strings do not require a route definition change.
7. No new task status model -- TASK_STATUSES already covers every value Overview links to.
8. No new RBAC behavior -- role-scoping (e.g. requester-owns-own-tasks) remains exclusively
   server-side in task_api.py, unchanged and untouched.
9. No FE.1D navigation/microcopy/IA implementation of any kind.
10. No Overview redesign -- ExecutiveOverview.tsx's existing tile links are the trigger for this
    work, not something this stage's future implementation should restructure.
11. No Delivery / Reminder / Notifications / Pipeline implementation -- unrelated future scope.
12. No fake counts or fake controls -- the list must continue to render exactly what
    taskApi.list() returns; no client-side-only enforcement standing in for a real check.
```

## Existing-data-only confirmation

No new backend capability is required. `GET /tasks?status=<value>` is the same endpoint TaskList's
own `Status` dropdown already calls today via `taskApi.list(filters)`. This stage is purely about
initializing existing frontend state from the URL, not about adding new data or new API surface.

## Dependencies already satisfied

```text
1. react-router-dom is already a project dependency (used throughout the Admin Console, including
   BrowserRouter with basename="/admin" in main.tsx) -- useSearchParams requires no new package.
2. TASK_STATUSES (apps/admin-console/src/tasks/taskTypes.ts) already contains every status value
   Overview's tiles link to -- no new enum entries needed.
3. taskApi.list() (apps/admin-console/src/tasks/taskClient.ts) already accepts a status filter and
   already builds the correct query string via filterQuery() -- no client changes to the API layer
   needed.
```

## Statement

Contract/boundary document only. No frontend runtime code changed. No backend/API/database/workflow
change. No new endpoint. Codex implementation not authorized by this document. FE.1D not authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
