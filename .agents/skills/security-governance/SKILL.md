# Skill: Security / Governance

> **Process documentation only. No backend/frontend runtime change. No production action.**

Owner: all partners; enforced primarily by Claude Code (Security/Governance Gate,
`.agents/skills/stage-gate/SKILL.md` §5). These restrictions apply to every stage, every role, and
every environment — they are not stage-specific and are not waivable by any partner other than the
Product Owner, and only for the specific documented exceptions below.

## Hard restrictions

```text
1. No production action without explicit Product Owner authorization.
2. No workflow dispatch / resume unless the stage explicitly authorizes it.
3. No external action (GitHub write, Discord/Slack/Telegram send, LLM call to a real external
   provider, or any other outbound integration) unless explicitly authorized.
4. No approval bypass — approval-required paths stay approval-required.
5. No client-side-only RBAC as security. Server-side RBAC is always the sole access-control
   authority; a UI hiding a control is a convenience, never a substitute for a server-side check.
6. No secrets, tokens, .env values, internal IPs, SSH aliases, private URLs, or credentials in
   docs, screenshots, logs, reports, examples, or code. Use neutral labels ("test host", "internal
   test runtime", "admin console local tunnel", "sandbox repo") in anything committed.
7. No hiding required audit/safety evidence. Presentation may relocate a technical field to an
   expandable/hover detail; it may never remove a safety-relevant signal from the reachable UI.
8. No fake controls in placeholders. A placeholder states "Not yet available," the specific
   required stage/contract, and "No workflow action available" — it never renders a button or
   control that appears actionable but silently does nothing (or worse, does something).
9. production_executed_true_count must remain 0 unless a stage has explicit Product Owner
   authorization to perform a real production action and records that authorization.
```

## Only the Product Owner may authorize an exception

Every restriction above is enforced by default. The only path past any of them is an explicit,
scoped Product Owner authorization recorded in the stage's own documentation (e.g. "授權部署 merged
main 到 test runtime" scopes a deployment authorization; it does not imply a production authorization
or a workflow-dispatch authorization). An authorization for one action does not imply authorization
for another. See `docs/process/stop-conditions.md` for what happens when a stage's request appears to
require an exception that hasn't been granted.

## Verification expectations

Every stage that touches runtime code, backend, frontend, or deployment must record, at minimum:

```text
- Secret scan result (critical/high/informational counts).
- production_executed_true_count before and after (or "N/A, no runtime touched" for docs-only
  stages).
- Workflow dispatch/resume: triggered or not.
- External action: triggered or not.
- Whether any forbidden path (backend, API, database, workflow, policy, approval, audit, infra)
  was touched.
```

A documentation-only or governance-only stage (like this one) still states these explicitly as "not
applicable / none" rather than omitting them — silence is not evidence.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
