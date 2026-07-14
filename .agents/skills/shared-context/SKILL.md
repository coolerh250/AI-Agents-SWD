# Skill: Shared Context

> **Process documentation only. No backend/frontend runtime change. No production action.**

Owner: all partners (Claude Code, Claude Design, Codex, and any future partner). This skill defines
what must be synced and reviewed before any task begins, and what counts as authoritative shared
context on this project.

## Required before starting any task

```text
1. Pull latest main (`git checkout main && git pull --ff-only origin main`).
2. Review source/progress.md (at least the tail relevant to the current/most recent stages).
3. Review the relevant subset of:
   - docs/design/<stage>/
   - docs/contracts/<stage>/
   - docs/frontend/<stage>/
   - docs/handoffs/<stage>/
   - docs/test/
   - docs/decisions/
   - .github/ (workflows, PR template)
4. Review related PRs / branches named in the task prompt or discoverable via
   `git branch -a` / `git ls-remote --heads origin` for the same stage family.
5. If a stage manifest exists for this stage (docs/stages/ convention, see
   .agents/skills/stage-gate/SKILL.md), read it in full.
```

## What is and is not source of truth

```text
IS source of truth:
- main (the merged, deployed state).
- source/progress.md (stage-by-stage record of what actually happened).
- docs/decisions/ (recorded Product Owner decisions).
- Any doc merged to main, including design/contract/frontend/handoff docs.

IS NOT source of truth on its own:
- Local-only notes, scratch files, or anything not committed and pushed.
- A Draft PR / unmerged branch — readable as proposed content and reviewable, but not binding
  until either (a) merged to main, or (b) explicitly referenced as accepted by a decision record
  under docs/decisions/ or a stage's own progress.md entry.
- Chat/session memory of any partner — a partner's recollection of an earlier conversation is
  not a substitute for reading the actual current files.
```

See `docs/process/source-of-truth-policy.md` for the full policy this skill implements.

## Conflict rule

If the task prompt conflicts with what the shared docs actually say (e.g. a prompt assumes a
decision that a merged doc contradicts, or names a commit/state that does not match current
`main`), **stop and report the conflict** before proceeding. Do not silently pick one side. Do not
proceed on the assumption that the prompt is more current than the repo — verify which one actually
is, and say so.

## Evidence this skill requires

Every stage's completion report must include a **Shared Context Preflight** section (latest main
reviewed, shared docs reviewed, related PRs/branches reviewed, new information found, conflicts
found, how new information affected the task) — see
`docs/stages/context-receipt-template.md`.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
