# Critical Path and Dependency Map — Project Completion Master Plan

> **Consolidated planning document only. No runtime code, no backend, no API, no database, no
> workflow, no new endpoint/route, no merge of any alignment branch, no deployment performed by
> this document.**

## Critical path (confirmed by all three partners, no conflict)

```text
M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7
```

## Current position

```text
M0: CLOSED.
M1: PARTIALLY complete. 66B and 66C done and shipped. Step 66C.4 (Reminder/Expiry) is the single
    remaining item and is READY_TO_START — the next item ON the critical path.
M2-M7: not started.
```

**The project's most recently completed execution capacity (FE.1D-S1 Navigation Polish, and the
FE.1D design/technical-readiness/boundary merge) is entirely OFF the critical path.** It improved
the Admin Console's presentation layer but did not unblock Step 66C.4 or any milestone after it.
This is the most important standing finding carried into this Master Plan.

## Technical dependency map

```text
66C.4-P (Claude Code planning) -> 66C.4-BE (Claude Code backend/workflow implementation) ->
  66C.4-BE-R (Claude Code review) -> 66C.4-FE (Codex frontend slice, only if explicitly
  authorized) -> 66C.4-VP/POV/MD (preview/PO validation/merge-deploy)
  -> the last M1 gap; Claude Code is the primary implementation owner (scheduler + existing
     clarification_expired transition are Claude-Code-owned backend/workflow work); Codex's role
     is limited to the explicitly authorized frontend slice. No dependency on 66D.

66C.4 -> 66D-ARCH (Delivery model/API contract)
  -> M2 cannot begin its UI design as pixel-final before the data model/API contract is decided.
     This is a categorical, unanimous requirement across all three partners (Claude Code:
     "Yes, categorically" in alignment-statement.md; Claude Design: "the data shape is Claude
     Code's contract... no M2 surface is built beyond a compliant placeholder until that contract
     exists"; Codex: FE-R1 "High" severity risk, "Frontend should not merge Delivery Inbox or
     Delivery Detail real UI before that freeze").

66D-ARCH -> 66D-DESIGN (Delivery UX)
  -> the design-collaboration/SKILL.md chain (design -> Claude Code review -> Product Owner
     decision -> Codex authorization) applies exactly as it did for FE.1C/FE.1D, now to M2 instead
     of cosmetic polish.

66D-DESIGN -> 66D implementation (backend then frontend slices)
  -> backend endpoints/data model land first (already Claude-Code-owned via 66D-ARCH); frontend
     slices follow the FE.1D-S1 small-PR precedent (one bounded, reviewable slice at a time).

66D implementation -> 66E (team orchestration/RBAC, M3)
  -> "multi-role control" is largely about who may accept/reject/escalate a delivery; the
     fixed-team integration assumes tasks flow all the way to delivery.

66E -> 66F/66G (notification/action/channel contract, M4)
  -> Action Center's primary queues (Approvals, DLQ, Delivery review) are M2/M3 artifacts; the
     shell must not be built before those queues have real data.

66F/66G -> 66H (controlled pilot, M5)
  -> a pilot's entire value is exercising the full M1-M4 loop with a real operator.

66H -> M6 (production hardening)
  -> intentionally placed AFTER the pilot: hardening a substrate before knowing the pilot didn't
     reveal a design flaw wastes the hardening effort (matches this project's own established
     caution in the Stage 60-63A dry-run rehearsals, which were deliberately kept reversible for
     exactly this reason).

M6 -> M7 (production rollout)
  -> standard: cutover, operator training, monitoring handoff, after all nine production-ready
     conditions are simultaneously true.
```

## Backend/API/data-model requirements per milestone (summary; full detail in
canonical-milestone-manifest.md)

```text
M0: none beyond documentation/hygiene.
M1 (66C.4): scheduler process + notification hook; no new task-status value.
M2 (66D): new delivery-package/acceptance-gate data model; new 6-action endpoints; Approvals/
  DLQ/Retry UI reads existing already-running backend services (a UI-and-thin-API gap, not a
  backend-build-from-scratch gap).
M3 (66E, Team RBAC): assignment-logic/data-model change for fixed-team routing; expose existing
  TASK_ROLES + 66A.3 6-role matrix through a real endpoint.
M4 (66F, 66G): new Slack/Telegram gateway services (same pattern as discord-gateway); a read
  aggregation/composition endpoint across Approvals/DLQ/Delivery-review.
M5 (66H): no new backend surface expected; gaps found become new, scoped backend work.
M6: zero product-feature backend change — entirely platform/infrastructure (K8s/Helm/ArgoCD, real
  secret store, Backup/DR remediation, Postgres auth hardening).
M7: no backend change — rollout/operational milestone.
```

## Non-critical-path work that may run in parallel without risk

```text
FE.1D-S2 (if the Product Owner wants it standalone) — touches only Admin Console display strings,
  zero overlap with 66C.4/66D backend or data-model work.
Any further governance/production-readiness dry-run rehearsal work (extending the Stage 60-63A
  kind/ArgoCD sandbox exercises) — useful preparation for M6, explicitly non-production and
  reversible, carries no risk of interfering with M1/M2 backend work. Must not be mistaken for M6
  itself.
```

## Statement

Consolidated planning document only. No runtime code, no backend, no API, no database, no workflow,
no new endpoint/route, no merge of any alignment branch, no deployment performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
