# Product Owner Decision Record — DESIGN-66UI.3

> Owner: Claude Design (recording the Product Owner's verdict). Binding direction reference for the
> follow-on Phase 1 detailed design brief. Does not authorize Codex implementation.

## Verdict: Hybrid (A + B + C principles)

- **Direction A — AI Team Command Center** → used for **Dashboard / Overview / cross-task
  operations**.
- **Direction B — Agent Workspace** → used for **Task Detail / Workroom / Clarification / future
  Delivery Review**.
- **Direction C — Executive Product Console** → applied as **language & style principles**
  throughout: simplified product language, calmer safety posture, better visual hierarchy, reduced
  engineering-field exposure. (Adopted as principles, not as a separate structural layout.)

This matches Claude Design's recommendation (A + B hybrid with C's language principles) and the
Product Owner's stated priority of single-task collaboration depth.

## Delivery Package decision (resolves the preflight conflict)

- **Keep Delivery Package under Platform Ops.** (Confirms the deployed, PO-validated state.)
- **Keep Delivery Inbox / Delivery Detail under Deliveries** (placeholders).
- **Do not merge** Delivery Package with Delivery Inbox until the Step 66D contract exists.
- The earlier 66UI.2 "decision #2" (move Delivery Package to Deliveries), which lived only on the
  unmerged PR #2, is **superseded** by this decision.

## PR #2 decision

- **Close PR #2** (`design/66ui2-navigation-ia`) as **superseded** by the merged Navigation / IA
  implementation now on `main`.
- **`main` / test-runtime state is the source of truth.**

## Next design task (this decision authorizes)

Claude Design prepares a **Phase 1 detailed design brief** covering:

```text
- global product visual language
- calm safety posture
- Overview cleanup
- navigation visual polish
- engineering-field reduction
- product microcopy improvement
```

Delivered under `docs/design/66ui4-phase1-product-visual-language/` (new branch
`design/66ui4-phase1-product-visual-language`). **Codex implementation is NOT authorized yet** —
the Phase 1 brief goes through Claude Code architecture review, then an explicit Product Owner
authorization, before any implementation.

## Process note — keep the record on `main` authoritative

The preflight conflict this stage surfaced (decision #2 lost on an unmerged PR) is a systemic risk:
design decisions recorded only on unmerged draft PRs do not become the project record. Recommend the
Product Owner have the design PRs (#1 66UI.1, #4 66UI.3, and the upcoming Phase 1 PR) **merged to
`main`** after Claude Code review, so `main` remains the single source of truth and design decisions
stop diverging from what ships. Flagged, not actioned — merge authorization is the Product Owner's.

## Statement

Decision record only. No runtime code. No production action. No Codex implementation authorized by
this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
