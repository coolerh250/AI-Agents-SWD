# Source-of-Truth Policy

> **Process documentation only. No backend/frontend runtime change. No production action.**

This policy states, unambiguously, what counts as authoritative on this project. It exists because
multiple prior stages found decisions recorded only on unmerged Draft PRs diverging from what
actually shipped — most concretely the Step 66UI.2-FE.1 Delivery Package placement gap (a decision
made on an unmerged `design/66ui2-navigation-ia` PR did not carry forward correctly) and the
systemic risk Claude Design itself flagged in
`docs/design/66ui3-product-ux-visual-direction/product-owner-decision-record.md`.

## What is authoritative

```text
- `main` is the source of truth for implemented and accepted state. If it isn't merged to main,
  it isn't shipped, regardless of how complete or reviewed it looks on a branch.
- `source/progress.md` records stage status — what was done, what was verified, what gate result
  each stage reached. It is the chronological ledger of record.
- `docs/decisions/` records Product Owner decisions that outlive a single stage (ADRs). A decision
  recorded here is binding going forward until superseded by a later decision recorded the same
  way.
```

## What is not authoritative on its own

```text
- Draft PRs are discussion artifacts, not source of truth, until either:
  (a) merged to main, or
  (b) explicitly referenced as accepted by a decision record under docs/decisions/ or a stage's
      own source/progress.md entry (as happened for the 66UI.3 Hybrid decision, which was
      accepted-and-cited before its own PR was merged — the citation, not the merge state, is
      what made it binding for the next stage).
- Local-only files (uncommitted, unpushed, or existing only in a chat session) are not
  deliverables and are not shared context for any other partner.
- A partner's memory of a previous conversation is not a substitute for reading the current state
  of the actual files.
```

## Superseded PRs

A design or implementation PR that has been replaced by a later decision must be **closed or
clearly marked superseded** — left silently open with stale content is exactly the divergence risk
this policy exists to prevent. See `docs/design/66ui4-phase1-product-visual-language/design-pr-source-of-truth-review.md`
for a worked example of this assessment (PR #2 closed-as-superseded per the Product Owner's own
recorded decision).

## Conflict resolution

If a task prompt, a partner's assumption, or a Draft PR's content conflicts with what `main` /
`source/progress.md` / `docs/decisions/` actually say, the merged/recorded state wins by default.
Stop and report the conflict rather than resolving it silently — see
`docs/process/stop-conditions.md` §"main conflicts with Draft PR decision."

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
