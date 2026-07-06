# E2E Staging Operator Authorization Template (Step 65G.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — this template is filled in by the operator to authorize Step 65G.2.**

Step 65G.2 must **not** run until the operator provides an explicit authorization naming each item
below. Claude Code does not self-authorize any of these.

## Authorization checklist (operator fills in)
```
Step 65G.2 — Controlled E2E Staging Workflow Execution — operator authorization

- Fresh intake execution ..................... [ ] authorized  (staging, production_effect=false)
- GitHub sandbox draft PR allowed ............ [ ] yes  [ ] no
    (if yes: sandbox repo coolerh250/AI-Agents-SWD-sandbox, draft only, no merge)
- Discord staging notification allowed ....... [ ] yes  [ ] no
    (if yes: MySanbox / #general, [STAGING] prefix)
- Anthropic budget/audit LLM calls allowed ... [ ] yes  [ ] no
    (through the platform budget/audit rail only)
- Maximum LLM call count ..................... [ ____ ]  (planned minimum: 1)
- Maximum LLM cost (USD) ..................... [ ____ ]  (planned cap: <= $1)
- Maximum Discord sends ...................... [ ____ ]  (planned: 1)
- Maximum GitHub draft-PR flows .............. [ ____ ]  (planned: 1)
- Operator UI validation after run ........... [ ] operator will validate the formal pages
- Direct diagnostic external calls ........... FORBIDDEN unless separately authorized here: [ ____ ]
```

## Standing constraints (not negotiable by this template)
- No production action, no production deploy/sync/secret, no production data, no customer/personal
  data, no merge/release/tag, no image push, no public exposure, no volume deletion.
- All real GitHub/Discord/LLM calls go through their controlled rails (65D/65E/65F).
- No automatic retry of any external call.
- `production_executed_true_count` must remain 0.

## After authorization
Once the operator returns this template completed, Step 65G.2 executes strictly within the
authorized counts and caps, then resets to safe (see
[e2e-staging-abort-and-reset-plan.md](e2e-staging-abort-and-reset-plan.md)). **Claude Code must not
decide staging functional acceptance** — that is the operator's Step 65I verdict.

## This stage's posture
Planning only. No workflow execution, no GitHub write, no Discord send, no LLM call, no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
