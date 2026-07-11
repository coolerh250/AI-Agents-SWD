# Step 66C.2 — Operator Validation Request

> **Claude Code does not decide operator acceptance. This is a request for the operator's own
> verdict.**

## How to access

SSH-tunnel to the test host as usual (see your own SSH configuration), then open the Admin
Console at `http://localhost:8000/admin/` and navigate to **Tasks** → open any task → **Open
Workroom**.

If you'd like to see a clarification in the workroom, ask Claude Code to create one via the API
first (the create-clarification UI is deferred in this stage — see `step66c2-known-gaps.md`), then
reload the Workroom page.

## Please verify

| # | Check | Your observation |
| --- | --- | --- |
| 1 | Can open a task detail page | |
| 2 | Can click "Open Workroom" | |
| 3 | Can see workroom messages | |
| 4 | Can post a human message | |
| 5 | Can see a clarification question | |
| 6 | Can answer a clarification | |
| 7 | Can see the clarification's status change to "answered" | |
| 8 | Can see `dispatch_enabled: false` | |
| 9 | Can see `resume_dispatch_enabled: false` | |
| 10 | Can see the test-role / safety banner | |
| 11 | Message content appears as plain text (not rendered as HTML/links) | |
| 12 | No workflow dispatch occurred anywhere during your walkthrough | |
| 13 | No workflow resume occurred anywhere during your walkthrough | |
| 14 | `production_executed_true_count = 0` (Safety Center page, or ask Claude Code to show `/operations/safety`) | |

## Required response

Please reply with one of:

```
VISIBLE
NOT_VISIBLE
PARTIAL_WITH_GAPS
```

If `PARTIAL_WITH_GAPS`, please note which of the 14 items above were not visible/working as
described.

## Statement

This is a request only — Claude Code does not decide operator acceptance. No workflow dispatch, no
workflow resume, no external action, no production action occurred in preparing this request.
production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
