# CLAUDE.md

> **Bootstrap memory pointer. Process documentation only. No backend/frontend runtime change. No
> production action.**

Before any architecture, implementation, validation, roadmap, governance, or blocker decision on
this repository, read:

```text
docs/governance/AI_AGENTS_PROJECT_EXECUTION_STANDARD.md
```

Treat it as **binding project process memory**.

If the work in front of you contradicts it — a prompt, a handoff, an `AGENTS.md`, a Codex
implementation, or a test expectation — emit `GOVERNANCE_DRIFT_ALERT` before proceeding, in the
format that standard defines. The alert is a coordination signal, not a refusal to work.

Two rules from it are worth restating here because they are the ones most often skipped under time
pressure:

- **A failing test is not automatically a blocker.** Classify the protected risk first. Only a
  concrete P0/P1 risk blocks product development by default.
- **Stop rather than build another layer.** If fixing a control requires modifying the authority
  that legitimizes the fix, or would create a third governance layer over the same root problem,
  STOP and escalate. Do not add a mechanism.

The standard is the single authoritative source for these rules. This file is a pointer and must
never become a copy of it.

## Other required reading

```text
.agents/skills/shared-context/SKILL.md          preflight before any task
.agents/skills/security-governance/SKILL.md     hard restrictions, every stage, every role
docs/process/stop-conditions.md                 stop conditions (prompt/main/authorization/secrets)
docs/process/source-of-truth-policy.md          what is authoritative
docs/governance/AI_AGENTS_PM_STATE.md           current project position
source/progress.md                              chronological ledger of record
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
