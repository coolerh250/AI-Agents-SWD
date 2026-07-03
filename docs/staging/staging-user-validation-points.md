# Staging User Validation Points (Step 65A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Documentation only. Claude Code records operator decisions; it does not self-accept.**

Defines where the operator/user must be asked to confirm or authorize during the Step 65 track.
Each is an operator-owned decision; Claude Code stops and records it.

## Validation / authorization points
| When | What the operator confirms / authorizes |
|---|---|
| **After 65A** | Confirms the functional-coverage **scope** ("all functions" = which domains). |
| **Before 65C** | Confirms the sandbox **credentials / resources** to provision. |
| **Before 65D** | Authorizes controlled **GitHub sandbox write** (sandbox repo only). |
| **Before 65E** | Authorizes controlled **staging notification send** (test channel only). |
| **Before 65F** | Authorizes staging **LLM key usage and quota** (non-prod key). |
| **During 65G** | Validates the **E2E output** on the formal Admin Console + any external artifacts. |
| **During 65H** | Authorizes each **failure / governance scenario**. |
| **At 65I** | Gives the **staging functional acceptance verdict** (PASS / PASS_WITH_ACCEPTED_GAPS / FAIL). |

## Rules
- No live external integration is enabled without the operator authorization above.
- No secret is created/stored without the operator confirming the sandbox resource.
- Operator visual validation (65G) is based on the **formal** product pages, not Demo Evidence.
- Claude Code must not decide staging functional acceptance or production readiness.

## Immediate next ask (after 65A)
Operator confirms the functional-coverage scope (the domains in the coverage matrix) and which
external integrations are in scope for 65D–65F, before 65B/65C begin.

## Posture
Documentation only. No runtime change, no integration enablement, no secret creation, no production
action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
