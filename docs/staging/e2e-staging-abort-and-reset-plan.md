# E2E Staging Abort & Reset Plan (Step 65G.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — recovery is planned here, not executed. No reset is run in this stage.**

Abort conditions and reset expectations for Step 65G.2.

## Abort conditions (stop immediately if any occurs)
- `production_executed_true_count` changes from 0.
- The GitHub target is **not** the sandbox repo `coolerh250/AI-Agents-SWD-sandbox`.
- The Discord target is **not** the staging channel `MySanbox / #general`.
- Any LLM call attempts a **direct / diagnostic** path (bypassing the budget/audit rail).
- The LLM budget cap is missing or not in `block` mode.
- A secret value appears in any log or output.
- The workflow attempts a **production deployment** (or any real deploy).
- Any **unexpected external write** occurs (beyond the authorized draft-PR flow / one notification /
  one LLM call).
- More than the authorized **call / send / write count** is attempted.
- The Admin Console cannot show the required evidence on the formal pages.

## On abort
- Stop the current step; do **not** auto-retry.
- Capture the failing state read-only (safety snapshot, the offending record).
- Report to the operator and await instructions — do not self-continue.

## Reset expectations (after the run, or on abort)
- All live flags reset to safe:
  - GitHub live mode **disabled** (`SANDBOX_GITHUB_LIVE=false`); no merge/release/tag/deploy left
    pending.
  - Discord real-send flag **disabled** (`RUN_REAL_DISCORD_TEST=false`); `SECRET_PROVIDER` back to
    its baseline.
  - LLM real-call flags **not left persistent** (ephemeral only) / rail-only mock state restored
    (`LLM_PROVIDER=mock`); any budget policy created for the run set to `inactive`.
- **No production action**; no merge / release / tag / deploy; no image push.
- `/operations/safety` re-checked read-only: `production_executed_true_count=0`,
  `llm_real_enabled=false`, `discord_external_send_enabled=false`,
  `sandbox_github_draft_pr_live_mode_enabled=false`.
- Only the minimal affected service(s) recreated if a temporary env flag was applied — never a
  full-stack restart, never `down` / `down -v` / volume deletion.

## Not executed here
No abort or reset is performed in Step 65G.1 — this document only plans them.

## This stage's posture
Planning only. No workflow execution, no GitHub write, no Discord send, no LLM call, no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
