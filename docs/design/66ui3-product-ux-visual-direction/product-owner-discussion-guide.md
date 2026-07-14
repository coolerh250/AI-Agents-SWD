# Product Owner Discussion Guide — DESIGN-66UI.3

> Owner: Claude Design. This stage ends in a discussion, not implementation. Zachary (Product
> Owner) uses this to choose a direction. **No Codex implementation is authorized by this stage.**

## Decision requested

Choose one:

- [ ] **Direction A — AI Team Command Center** (`direction-a-ai-team-command-center.md`)
- [ ] **Direction B — Agent Workspace** (`direction-b-agent-workspace.md`)
- [ ] **Direction C — Executive Product Console** (`direction-c-executive-product-console.md`)
- [ ] **Hybrid** — describe which elements of which directions
- [ ] **Needs another round** — what's missing

Claude Design's recommendation (for reference, not a default): a **Hybrid of A + B** — Direction A's
attention-first command-center framing for the cross-task surfaces (Overview, Operator Center),
wrapping Direction B's Agent Workspace for the single-task Workroom (the product's core). This
matches the earlier 66UI.1 Hybrid intent (Option 1 IA + Option 2 task workspace) and the Product
Owner's stated priority of single-task collaboration depth. Direction C's *language and calm-safety*
principles should be adopted regardless of the structural choice.

## Questions to answer

1. **Primary identity.** Should the Admin Console feel primarily like an **AI team command center**
   (A), an **agent workspace** (B), or a **simplified executive product console** (C)? This is the
   core question.
2. **Density vs. simplicity.** Are the daily users power users who want density and cross-task
   awareness (favors A/B), or should the primary surface be simplified for mixed/non-technical
   audiences (favors C)?
3. **Palette / theme.** Keep the existing dark ground (A/B), or treat this as an opportunity to
   revisit palette/theme, possibly lighter or dual-theme (C)? A palette change adds scope and risk.
4. **Start with Phase 1?** Do you agree the first implementation slice should be the
   direction-agnostic Phase 1 (calm safety posture + design language + attention-first Overview),
   which needs no backend change — regardless of direction chosen?
5. **Agent identity.** Are you comfortable introducing visible agent identities + activity states
   (Intake/Requirement/Development/QA/DevOps) as a core product device, sourced from existing
   server data? (This is the main lever for making the "AI team" visible.)

## Conflict to resolve (surfaced in preflight — needs your call)

**Delivery Package placement — an inconsistency between two of your own past decisions:**

- In the **66UI.2 design discussion** you chose "decision #2": move Delivery Package **into the
  Deliveries group**. That is recorded only on the **unmerged Draft PR #2** branch
  (`design/66ui2-navigation-ia`, `product-owner-decision-record.md`).
- At **FE.1 UI validation** you then validated the deployed shell **VISIBLE**, which has Delivery
  Package **under Platform Ops** (validation record item #3: "Delivery Package renders under
  Platform Ops … accepted"). That is what is merged to `main` and live on the test runtime, and
  what this DESIGN-66UI.3 prompt describes as the current state.

So the live, merged, PO-validated state (**Platform Ops**) contradicts the earlier unmerged
decision (**Deliveries**). Per `docs/process/github-collaboration-hub.md` ("if it isn't in this
repository, it isn't part of the project record"), the on-`main` state is authoritative, so this
review treats **Platform Ops** as the baseline. Two things need your decision:

1. **Which placement is intended going forward** — leave Delivery Package under Platform Ops
   (current live state), or still move it into Deliveries (original 66UI.2 decision #2)?
2. **What to do with Draft PR #2** — it is now stale/divergent from `main` (its decision-record and
   page-grouping edits conflict with what shipped). Recommend either closing it, or reconciling its
   docs to match the shipped Platform Ops placement, so the repo record stops contradicting itself.

This is a small nav sub-item and does **not** block choosing a visual direction — but it should be
settled so the project record is consistent.

## What happens after you choose

1. Claude Design turns the chosen direction (or Hybrid) into a Phase 1 detailed design brief
   (calm safety posture + design language + Overview), following the collaboration protocol.
2. Claude Code reviews it (architecture/safety); confirms no contract change (Phase 1 needs none).
3. **You** authorize Codex to implement Phase 1.
4. Later phases (Workroom, Clarification, Delivery, Operator) each repeat the cycle; Delivery and
   Reminder stay placeholder-only until their 66D / 66C.4 contracts exist.

**Do not proceed to detailed design or Codex implementation until you choose a direction here.**

## Statement

Design discussion guide only. No runtime code. No production action. No Codex implementation
authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
