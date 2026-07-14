# Partner Handoff Standard

> **Process documentation only. No backend/frontend runtime change. No production action.**

Every partner (Claude Code, Claude Design, Codex, and any future partner) closes out a stage with a
handoff following this standard, so the next partner — or the same partner in a future session with
no memory of this one — can pick up the work from the repo alone.

## Required sections

```text
What I read
What changed since last stage
What I changed
What I did not change
What assumptions I made
What requires Product Owner decision
What requires Claude Code review
What Codex must not implement yet
Security / governance impact
Shared artifacts produced
Known gaps
Next recommended step
```

## Guidance per section

- **What I read** — the actual files/commits reviewed, not a paraphrase of what was probably
  relevant. This is the context receipt's content, restated in handoff form.
- **What changed since last stage** — anything discovered during this stage's Shared Context
  Preflight that wasn't already known when the stage began.
- **What I changed / What I did not change** — an explicit boundary, not just a diff link — state
  plainly what was left untouched, especially anything adjacent that might look related.
- **What assumptions I made** — any judgment call taken without an explicit instruction (e.g.
  choosing not to create a diverging duplicate file to avoid a foreseeable merge conflict).
- **What requires Product Owner decision / Claude Code review / Codex must not implement yet** —
  the explicit gates the next step must pass through, so no partner mistakes "I finished my part"
  for "this is fully authorized."
- **Security / governance impact** — restate the relevant facts even when the answer is "none":
  workflow dispatch/resume, production/external action, `production_executed_true_count`, secret
  scan result.
- **Shared artifacts produced** — every doc/script/test file this stage added or updated, by path.
- **Known gaps** — anything explicitly deferred, with enough detail that a future partner
  understands why it wasn't done now, not just that it wasn't.
- **Next recommended step** — a concrete suggestion, understood as a recommendation, not a
  self-authorization to proceed.

## Relationship to completion reports

This standard's sections map closely onto the completion-report formats used throughout the
project's stage prompts; a stage-specific completion report format given in a prompt takes
precedence over this generic list, but should still cover every item above somewhere in its
structure.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
