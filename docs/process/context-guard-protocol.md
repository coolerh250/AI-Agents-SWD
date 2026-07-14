# Context Guard Protocol

> **Process documentation only. No backend/frontend runtime change. No production action.**

This protocol defines the mechanism that keeps every partner (Claude Code, Claude Design, Codex, and
any future partner) synchronized with the actual current state of the repository, regardless of how
long any individual conversation/session has run or how much local-only state may have accumulated.
It exists because long context and unmerged Draft PRs have previously caused real divergence (see
`docs/decisions/README.md` process notes and the Step 66UI.2-FE.1 Delivery Package placement gap).

## Components

### 1. Shared Context Preflight

Every stage begins with the preflight defined in `.agents/skills/shared-context/SKILL.md`: sync
`main`, review `source/progress.md`, review relevant `docs/` subtrees, review related PRs/branches.
This is not optional and not satisfied by recalling a prior conversation.

### 2. Context Receipt

The preflight's result is recorded using `docs/stages/context-receipt-template.md` — a concrete,
checkable artifact, not an implicit claim. A stage's completion report includes this receipt (or an
equivalent "Shared Context Preflight" section following the same fields).

### 3. Stage Manifest

Where a stage manifest exists (`docs/stages/stage-manifest-standard.yaml` schema), it declares the
stage's scope, allowed/forbidden paths, authorization flags, and required evidence in a
machine-checkable form, reducing reliance on prose-only scope descriptions.

### 4. Source-of-truth review

Every stage confirms what is actually binding before acting on it, per
`docs/process/source-of-truth-policy.md` — `main`, `source/progress.md`, and `docs/decisions/` are
authoritative; a Draft PR or local note is not, unless explicitly promoted by an accepted decision
record.

### 5. Conflict rule

If the task prompt conflicts with what the shared docs/repo state actually show, **stop and report
the conflict** rather than silently resolving it in either direction. This is restated in every
skill and template in this pack because it is the single check most likely to be skipped under time
pressure.

### 6. Stop conditions

`docs/process/stop-conditions.md` enumerates the specific situations that require stopping for
clarification rather than proceeding. A partner encountering one of these must report it, not work
around it.

### 7. Verifier requirement

`scripts/verify_stage_gate_compliance.py` checks that this skill pack itself — the skills, process
docs, templates, and PR template sections — remains present and internally consistent. It does not
(and cannot) verify that a given partner actually read the files; that assurance comes from the
context receipt and the human/Product Owner review of completion reports.

## Future enforcement

This protocol is currently enforced by convention, completion-report review, and the compliance
verifier above — there is no CI gate yet blocking a PR that omits a context receipt or skips reading
a skill file. See `docs/process/stop-conditions.md` and this stage's own completion report §9 for
the recommendation to add CI enforcement in a future stage.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
