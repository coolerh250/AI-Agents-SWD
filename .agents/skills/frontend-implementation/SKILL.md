# Skill: Frontend Implementation

> **Process documentation only. No backend/frontend runtime change. No production action.**

Owner: Codex (subject); Claude Code (reviews and enforces boundary). This skill restates and
formalizes the frontend implementation boundaries already established in
`docs/process/role-responsibility-matrix.md` and prior stage boundary docs, as a repo-level skill
every partner can look up without depending on any single conversation's memory.

## What Codex owns

```text
Admin Console frontend implementation only, and only when explicitly authorized for that specific
stage: React components, routes, API clients, frontend tests, under apps/admin-console/.
```

## Working-from rules

```text
1. Codex must work from latest main — branch the implementation branch off main, not off a design
   branch.
2. Codex must not base an implementation branch on a design branch. Design branches
   (design/<stage>) are read-only reference material, never a merge/rebase parent for an
   implementation branch.
3. Codex may read a design branch or its Draft PR as reference material to understand intended
   direction, but implements only from the authorized contract/boundary docs
   (docs/contracts/<stage>/, docs/frontend/<stage>/codex-readiness-boundary.md), not from
   unreviewed design-branch content directly.
4. Codex must not modify backend, database, workflow, policy, approval, audit service, infra, or
   API contracts unless explicitly authorized by both Claude Code (technical boundary) and the
   Product Owner (direction) for that specific change.
```

## Deliverable rules

```text
1. Codex must produce shared artifacts under docs/frontend/<stage>/, docs/handoffs/<stage>/ (if
   applicable), docs/test/, and an update to source/progress.md. These are the only outputs that
   count as delivered work.
2. Local-only outputs (uncommitted branches, notes only in a chat session, files not pushed to
   origin) are not deliverables and do not satisfy any stage's completion criteria.
3. Every Codex PR must include, at minimum:
   - Tests (what was added/run, and the result).
   - Build result (npm run build / npm test, pass or fail).
   - A safety statement (workflow dispatch/resume, external action, production action — each
     explicitly "no" unless the stage authorized otherwise).
   - Known gaps (anything explicitly deferred, non-blocking).
   - Product Owner validation status (not yet validated / validated VISIBLE / etc. — Codex never
     self-declares this status, only records what it currently is).
```

## Authorization gate

Codex does not start implementing on its own initiative. Implementation requires: a design brief
that passed Claude Code's Design Review Gate, a contract/boundary doc from Claude Code scoping
exactly what may be built, and an explicit Product Owner authorization for that specific
implementation stage. See `.agents/skills/design-collaboration/SKILL.md` for the full chain.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action. No Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
