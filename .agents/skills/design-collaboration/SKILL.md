# Skill: Design Collaboration

> **Process documentation only. No backend/frontend runtime change. No production action.**

Owner: Claude Design (subject); Claude Code (reviews and enforces boundary). This skill restates and
formalizes the design boundaries already established in
`docs/process/role-responsibility-matrix.md` and prior stage boundary docs (e.g.
`docs/frontend/66ui2-navigation-ia/codex-implementation-plan-boundary.md`), as a repo-level skill
every partner can look up without depending on any single conversation's memory.

## What Claude Design owns

```text
- Information architecture (IA), navigation structure proposals.
- User flows and wireframes.
- Visual direction, tokens, layout, and component specs.
- Microcopy (product-language strings, tone, empty/error/loading copy).
```

## What Claude Design does not own

```text
- Claude Design does not modify runtime code — no apps/admin-console/src or any other runtime
  path.
- Backend behavior, RBAC rules, workflow behavior, deployment, production behavior.
- API/contract decisions — those are Claude Code's (docs/contracts/<stage>/).
```

## Review and authorization chain

```text
1. Claude Design produces a design brief/spec under docs/design/<stage>/.
2. Claude Code reviews it for architecture soundness, safety posture, and contract impact
   (Design Review Gate, .agents/skills/stage-gate/SKILL.md §3) — a review-only stage, no runtime
   code, no PR merge, no Codex authorization by itself.
3. The Product Owner chooses the final direction/decision, recorded under docs/decisions/ or the
   stage's own progress.md entry.
4. Only after both (2) passes and (3) is explicit does Codex become authorized to implement —
   and Claude Code sets the implementation boundary (docs/contracts/<stage>/,
   docs/frontend/<stage>/codex-readiness-boundary.md) before Codex starts.
```

**Codex cannot implement from a design brief just because it exists or reads as complete.**
Authorization requires both the Claude Code review passing and an explicit Product Owner
go-ahead — see `.agents/skills/frontend-implementation/SKILL.md` for what Codex itself must
observe.

## Handoff requirement

Every design stage's completion report follows
`docs/process/partner-handoff-standard.md` and states explicitly: what changed, what remains
undecided, what requires Claude Code review, what requires Product Owner decision, and what Codex
must not implement yet.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action. No Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
