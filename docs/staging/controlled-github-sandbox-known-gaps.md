# Controlled GitHub Sandbox Validation — Known Gaps (Step 65D)

> **Staging only — non-production only. No production action. No production secret. No production repo write.**

## Findings (resolved)
1. **Step 59 live flow committed nothing** → GitHub rejected the draft PR ("no commits between base
   and head"). **Fixed** (`ea52208`): `_create_live` now commits a non-production evidence file to
   the branch before opening the PR. This was the first-ever live execution of the flow; it had
   only been exercised in dry-run before.
2. **Allowlist targeted the main repo** (`AI-Agents-SWD`), not the sandbox repo. **Fixed**
   (`022b518`): retargeted to `AI-Agents-SWD-sandbox`.
3. **Sandbox/auth env vars not wired into the orchestrator container.** **Fixed** (`38e4fcd`):
   added them to the compose `environment` with safe defaults.
4. **Token initially lacked git permissions** (403). **Resolved by operator**: granted Contents
   (RW) + Pull requests (RW).

## Residual / follow-ups (non-blocking)
- **Draft PR #15 remains open** in the sandbox repo as validation evidence. The operator may close
  it and delete its branch `sandbox/ai-agents/…/0e3ae96ff64f` at any time (optional cleanup).
- The evidence-commit content is intentionally minimal (a metadata markdown). A future enhancement
  could attach the actual generated code artifact when the delivery pipeline produces one.
- Re-running 65D live requires re-enabling the flags + a runtime reload (documented), then reset.

## Posture
Sandbox-only controlled validation. No production action; no merge; `production_executed_true_count=0`.

## Status
Step 65D: **PASS**.

---
_Staging only — non-production only. No production action. No production secret. No production repo write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=sandbox-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
