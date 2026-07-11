# Operator Validation Handoff Template

> Append an entry to `docs/handoffs/<stage>/handoff-index.md` using this shape when Claude Code hands
> a deployed feature off to Zachary for final validation.

## Handoff: Operator Validation

- Stage: `<stage id>`
- Date:
- From: Claude Code
- To: Zachary (Operator)
- Deployed to: internal test runtime (see `docs/test/<stage>-test-deployment-record.md`)
- Validation request: link to `docs/test/<stage>-operator-validation-request.md`
- Operator response (once given): `VISIBLE` / `NOT_VISIBLE` / `PARTIAL_WITH_GAPS`
- Validation record: link to `docs/test/<stage>-operator-validation-record.md` (once recorded)

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
