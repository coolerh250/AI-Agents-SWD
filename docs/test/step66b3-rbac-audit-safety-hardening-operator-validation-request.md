# Step 66B.3 — Operator Validation Request

> **Claude Code does not decide operator acceptance. This is a request for the operator's own
> verdict.**

## How to access

SSH tunnel to the test host, then open the Admin Console:
```
ssh -L 8000:127.0.0.1:8000 aiagent-swd
```
Browse to `http://localhost:8000/admin/` and navigate to **Tasks** via the sidebar.

## Please verify

| # | Check | Your observation |
| --- | --- | --- |
| 1 | The role simulation banner is still visible on every task page | |
| 2 | The current actor/role is visible (e.g. "Current: test-operator as Requester") | |
| 3 | The role dropdown shows readable labels (e.g. "PM / Engineering Lead") rather than raw role strings | |
| 4 | A safety panel or safety fields (Environment, production_effect, requires_approval, dispatch_enabled, external_actions_enabled, production_executed) are visible on a task's detail page | |
| 5 | The `production_effect=true` warning still appears (check the box on `/tasks/new` or view a `production_effect=true` task) | |
| 6 | `dispatch_enabled: false` remains visible on task detail | |
| 7 | Switching to a role that cannot perform an action (e.g. Agent Operator trying to create a task) produces an understandable error message, not just a raw error code | |
| 8 | No workflow dispatch occurred anywhere during your walkthrough | |
| 9 | `production_executed_true_count = 0` (Safety Center page, or ask Claude Code to show `/operations/safety`) | |

## Required response

Please reply with one of:

```
VISIBLE
NOT_VISIBLE
PARTIAL_WITH_GAPS
```

If `PARTIAL_WITH_GAPS`, please note which of the 9 items above were not visible/working as
described.

## Statement

This is a request only — Claude Code does not decide operator acceptance. No workflow dispatch, no
external action, no production action occurred in preparing this request.
production_executed_true_count=0.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
