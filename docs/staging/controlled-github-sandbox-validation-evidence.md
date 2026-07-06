# Controlled GitHub Sandbox Validation — Evidence (Step 65D)

> **Staging only — non-production only. No production action. No production secret. No production repo write.**
> **Read-only evidence (masked). No secret value printed.**

Evidence captured around the real GitHub sandbox draft-PR validation on `10.0.1.32`.

## Readiness (orchestrator `/operations/github/sandbox-draft-pr/readiness`)
| Phase | live_mode_effective | credential_present | blocked_reason |
|---|---|---|---|
| Before enablement | false | false | live_sandbox_not_enabled |
| After enable + rebuild | **true** | **true** | **null** |
| After reset | false | true (token still present, inert) | live_sandbox_not_enabled |

## Allowlist (retargeted)
`/operations/github/sandbox-draft-pr/allowlist` → `coolerh250/AI-Agents-SWD-sandbox`
(key `ai-agents-sandbox`, base `main`, head prefix `sandbox/ai-agents/`, draft-PR only,
merge/release/deploy = false).

## Draft PR result (real)
- Orchestrator POST `/operations/github/sandbox-draft-pr` → `status=created`, `mode=live_sandbox`.
- **PR #15** — `https://github.com/coolerh250/AI-Agents-SWD-sandbox/pull/15`.
- GitHub read of PR #15: `state=open`, `draft=true`, `commits=1`, `changed_files=1`, base `main`,
  head `sandbox/ai-agents/prj-saas-user-management-module-15f51d/wi-0001/0e3ae96ff64f`,
  title `[Sandbox][Draft] PRJ-SAAS-USER-MANAGEMENT-MODULE-15F51D: Create user CRUD API`.

## Orchestrator record + safety
- `/operations/github/sandbox-draft-pr/requests` → a `created` record with pr#15 + url.
- `/operations/github/sandbox-draft-pr/safety` → `created_count=1`, `merge_enabled=false`.
- `/operations/safety` → `production_executed_true_count=0`.

## Credential handling
- The sandbox token was read from the env only (host), used in GitHub `Authorization` headers, and
  **never printed or committed**. Read-only GitHub diagnostics used the token in-header only.

## Reset
- `SANDBOX_GITHUB_LIVE=false`, `ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS=false`,
  `ADMIN_CONSOLE_TEST_AUTH_ENABLED=false`, `ADMIN_CONSOLE_AUTH_MODE=disabled`; orchestrator
  recreated; test-login returns `auth_disabled`; readiness `live_effective=false`.

## Status
Step 65D: **PASS**. `production_executed_true_count=0`. Not production readiness.

---
_Staging only — non-production only. No production action. No production secret. No production repo write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=sandbox-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
