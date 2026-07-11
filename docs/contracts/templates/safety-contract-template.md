# Safety Contract Template

> Copy into `docs/contracts/<stage>/safety-contract.md` and fill in. Owner: Claude Code.

## Stage

`<stage id>`

## Safety fields

State which endpoints return `dispatch_enabled` and/or `resume_dispatch_enabled`, and confirm both
are always `false` in this project's current scope — no endpoint in this stage triggers a workflow
dispatch or resume.

## Mandatory constraints (restate for this stage)

- No workflow dispatch.
- No workflow resume.
- No GitHub write.
- No Discord send.
- No Slack send.
- No Telegram send.
- No LLM call.
- No web call.
- No production action.
- `production_executed_true_count` remains `0`.

## Frontend rendering safety (if this stage touches user/agent-generated content)

- Plain-text rendering only — no `dangerouslySetInnerHTML`, no markdown-to-HTML, no URL
  auto-linking, unless separately reviewed and stated otherwise here.
- Input length limits enforced client-side, matching the backend's limits exactly.

## Statement

Contract specification only. No runtime code change implied by this document alone. No production
action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
