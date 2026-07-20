# Known Gap — Admin Console SPA Deep-Link / Hard-Refresh Fallback

> **Documentation only. No production action. No runtime code changed by this document.**

## Summary

Directly typing or pasting an Admin Console client-side route (any path other than the exact mount
root) into the browser address bar, or doing a hard refresh while on one, returns a raw backend 404
(`{"detail":"Not Found"}`) instead of loading the Admin Console SPA at that route.

## Discovery context

Found during Step 66UI.4-FE.1C.1-VP Product Owner UI validation, while testing checklist items 4–6
(directly pasting `/tasks?status=blocked`, `/tasks?status=clarification_needed`, and
`/tasks?status=unknown` into the browser address bar). Investigated live rather than assumed.

## Root cause (confirmed by source inspection and live reproduction, not guessed)

The Admin Console is mounted in `apps/orchestrator/src/main.py:260` as:

```python
app.mount("/admin", StaticFiles(directory=_admin_dir, html=True), name="admin-console")
```

(comment-dated to Stage 50, i.e. this predates every FE.1B/FE.1B.1/FE.1C/FE.1C.1 stage). Starlette's
`StaticFiles(html=True)` serves `index.html` only at the exact mount root (and for literal
`.html`-suffixed files); it does not provide a wildcard/catch-all fallback that rewrites unmatched
sub-paths back to `index.html`. A full-page browser navigation (typed URL, pasted URL, or hard
refresh) to any client-side route other than the root therefore hits the backend directly, finds no
matching route, and returns a plain 404.

Confirmed via live `curl` against the test runtime:

```text
GET /admin/            -> 200 (serves index.html)
GET /admin/tasks       -> 404 {"detail":"Not Found"}
GET /admin/tasks?status=unknown -> 404 {"detail":"Not Found"}
GET /admin/safety      -> 404 {"detail":"Not Found"}
GET /admin/overview    -> 404 {"detail":"Not Found"}
```

`/admin/safety` and `/admin/overview` were tested specifically to confirm this is a **general,
pre-existing platform limitation affecting every client-side route**, not something specific to
`/tasks` or introduced by Step 66UI.4-FE.1C.1 (TaskList Query Param Filter Support).

## What still works

Client-side navigation — i.e. clicking a `<Link>` inside the already-loaded SPA (React Router
intercepts the click, no full-page reload, no new HTTP request to the backend for that path) — is
unaffected. This includes:

```text
1. The Overview attention tiles linking to /tasks?status=clarification_needed and
   /tasks?status=blocked (Step 66UI.4-FE.1C).
2. TaskList's query-param-driven initial filter (Step 66UI.4-FE.1C.1), when reached via an
   in-app click rather than a typed/pasted URL or a hard refresh.
3. Every other in-app navigation link throughout the Admin Console.
```

The gap only affects: typing/pasting a deep-link URL directly into the address bar, hard-refreshing
while on a non-root route, and opening a deep link in a new tab/window from outside the SPA (e.g.
from a bookmark or a message).

## Impact on prior stages

```text
Step 66UI.4-FE.1C (Overview attention tiles) and Step 66UI.4-FE.1C.1 (TaskList query-param filter):
  both verified and validated correctly via their actual intended usage path (in-app click
  navigation). This gap does not invalidate either stage's PASS/VISIBLE verdict -- the deep-link
  behavior those stages implement works exactly as designed when reached the way a real user
  reaches it (clicking through the app), and this gap is not a regression introduced by either
  stage.
```

## Proposed remediation (not authorized, not scheduled)

Add a catch-all fallback route on the backend so that any unmatched path under `/admin/*` serves
`index.html` (letting React Router resolve the route client-side), while preserving the existing
behavior for real static asset paths (`/admin/assets/*`, etc.). This is a **backend** change (a new
or modified FastAPI route/exception handler in `apps/orchestrator/src/main.py`), not a frontend-only
change, and is therefore out of scope for any FE.1C/FE.1C.1-style frontend-only stage. It requires
its own explicit Product Owner authorization and Claude Code architecture review before
implementation.

## Status

```text
Blocking: no -- does not block any completed or in-flight stage's verdict.
Scheduled: no -- not yet authorized or assigned to a stage.
Tracking: this document. Should be referenced by a future stage's Shared Context Preflight if that
  stage proposes any Admin Console routing/deployment change.
```

## Statement

Documentation only. No production action. No runtime code changed by this document. No backend/API/
database/workflow change performed. No stage's prior verdict is altered by this record.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
