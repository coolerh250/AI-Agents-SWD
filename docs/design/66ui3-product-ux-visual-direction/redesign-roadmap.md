# Prioritized Redesign Roadmap — DESIGN-66UI.3

> Owner: Claude Design. A phased design roadmap. Each phase is a *design* stage that would each get
> its own brief → Claude Code review → Product Owner authorization → Codex implementation. **No
> phase is authorized for implementation by this document.**

## Sequencing principle

Order by **(engineering-signal removed) × (product value) ÷ (build risk & dependency)**, and put
work that has **no backend dependency first** so value lands without waiting on 66C.4 / 66D / 66S.
This reorders the prompt's suggested phases slightly — rationale given per phase.

## Phase 1 — Global de-engineering: safety posture + design language + Overview

**Why first:** the `SafetyStatusBar` raw-field dump appears on *every page* — fixing it removes the
single most pervasive engineering signal instantly, and it needs no backend change. Bundling the
token/hierarchy refinements and the attention-first Overview makes the whole app feel different for
the least risk.

- Calm safety **posture indicator** replacing the raw 12-field bar (server-computed, displayed-as-
  returned; detail on expand).
- Design-language refinements: surface elevation, two-density system, status-vs-safety color
  separation, microcopy pass (field names → product language).
- Overview dashboard: attention-first (decisions waiting / deliveries to review / blocked / risk).
- No backend dependency. Lowest risk, broadest visible impact.

## Phase 2 — Workroom / Task Workspace redesign

**Why second:** highest *product* upside — turns the log-like Workroom into real human–AI-team
collaboration (agent identity, role-differentiated messages, "waiting on you" state), and introduces
the agent-activity presentation that makes the product's premise visible. Depends on Phase 1's design
language existing.

- Workroom message treatment + agent identity + timeline primitive.
- Task Detail → task header (retire the raw `KeyValueTable` dump).
- Task List → triage-first list.
- (If Direction B/Hybrid) the task-workspace convergence — flagged to need its own implementation-
  plan review before Codex starts (per 66UI.2).
- Uses existing endpoints; no new contract. Agent-activity states must come from the server.

## Phase 3 — Clarification / Reminder UX

**Why third:** builds directly on the Phase 2 Workroom to make clarifications read as decision
requests. The **reminder/expiry** portion is gated on the 66C.4 contract and stays a compliant
placeholder until it exists — so the clarification-as-decision-request part (no backend dep) ships
now, the reminder/overdue part waits.

- Clarification decision-request card (no backend dep — ships with Phase 2/3).
- Reminder / overdue / expiry indicators — **placeholder until Step 66C.4 contract**.

## Phase 4 — Delivery Review UX

**Why fourth:** high product value (the acceptance desk), but **fully gated on the Step 66D
contract** — cannot move past placeholder until Claude Code publishes it. Design intent can be
detailed now; implementation waits.

- Delivery review "acceptance desk" design (Accept / Reject / Request Changes / Re-run QA as
  clearly-consequenced actions; evidence expandable).
- **Placeholder until Step 66D contract exists.**

## Phase 5 — Operator Center / Governance refinement

**Why last:** lowest engineering-signal-per-effort for the *product* feel (operators tolerate
density), and the unified Action Center depends on both 66D and 66C.4. Governance/audit readability
was partly handled in Phase 1; this phase finishes it.

- Audit evidence → human-readable events (hashes as detail).
- Operator Center consistency pass; unified Action Center **blocked on 66D + 66C.4**.
- Platform Ops: keep quiet; light consistency only.

## Dependency summary

| Phase | Backend dependency | Can design now | Can implement now (if authorized) |
| --- | --- | --- | --- |
| 1 — Safety/language/Overview | none | yes | yes |
| 2 — Workroom/Workspace | none (existing endpoints) | yes | yes (workspace convergence needs impl-plan review) |
| 3 — Clarification | none for card; 66C.4 for reminder | yes | card yes; reminder placeholder-only |
| 4 — Delivery Review | **66D contract** | design intent yes | placeholder-only until 66D |
| 5 — Operator/Governance | 66D + 66C.4 for unified Action Center | yes | audit/readability yes; Action Center waits |

## Recommended starting point

Phase 1, regardless of which direction the Product Owner selects — it is common to all three
directions, has no backend dependency, and removes the most-visible engineering signals fastest.
The chosen direction (A/B/C/Hybrid) mainly determines the emphasis and ordering of Phases 2–5.

## Statement

Design roadmap only. No runtime code. No production action. No Codex implementation authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
