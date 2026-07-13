# Product Owner Review Checklist — DESIGN-66UI.2

> Owner: Claude Design. The checklist Zachary (Product Owner / Operator) uses to accept or send back
> this Navigation / IA brief. Acceptance here means "the design is ready for Claude Code review and
> then Product-Owner authorization of Codex" — it is **not** authorization to implement.

## Acceptance checklist

| # | Criterion | Where addressed | ✅ / ⚠ / ❌ |
| --- | --- | --- | --- |
| 1 | Navigation grouping is clear (flat 28 → 7 legible groups) | `navigation-map.md`, `page-grouping.md` | ☐ |
| 2 | Workroom's weight is raised (dedicated Team Work group, no longer peer to Sandbox GitHub) | `navigation-map.md`, `role-based-entry-points.md` | ☐ |
| 3 | Platform Ops no longer competes with the core product surface (collapsed group, grouping-only) | `navigation-map.md` (collapse behavior), `page-grouping.md` | ☐ |
| 4 | Delivery / Reminder are NOT presented as usable (compliant placeholders only) | `placeholder-rules.md`, `page-grouping.md` | ☐ |
| 5 | Safety / audit / governance remain clearly visible | top-bar posture + Governance group; `role-based-entry-points.md`, `page-grouping.md` | ☐ |
| 6 | The design is suitable for Codex to build as a round-1 nav shell | `codex-implementation-notes.md` | ☐ |
| 7 | No route target / page behavior changes in round 1 | `migration-from-current-nav.md`, `design-brief.md` | ☐ |
| 8 | Placeholder policy (66D / 66C.4 / 66S / Coming later) followed exactly | `placeholder-rules.md` | ☐ |
| 9 | Role-based default entry points make sense per persona | `role-based-entry-points.md` | ☐ |
| 10 | `OperatorConsole` vs Approvals/DLQ resolved (separate pages under one group) | `design-brief.md`, `page-grouping.md` | ☐ |

## Open questions for the Product Owner

1. **Dashboard overlap.** Should the Overview `Dashboard` (extending `ExecutiveOverview.tsx`) and
   the Platform Ops `Operational Metrics` (`OperationalMetrics.tsx`) eventually merge into one
   dashboard, or stay as two? Round 1 keeps them separate; this does not block the nav shell.
   (Raised by Claude Code review §6.1.)
2. **DeliveryPackage placement.** This brief keeps `Delivery Package` under **Platform Ops** (legacy
   evidence record) and reserves the **Deliveries** group for the future 66D task-linked flow.
   Confirm that is what you want, or whether `Delivery Package` should instead appear inside the
   Deliveries group (still as a distinct, non-merged item).
3. **Empty Deliveries group in round 1.** The Deliveries group is entirely placeholder until 66D.
   Do you want it shown-but-marked in round 1 (current recommendation, makes the target IA legible),
   or hidden entirely until 66D ships?
4. **Security/Compliance cross-group span.** That role's material spans Governance (Safety/Audit)
   and Platform Ops (Identity/Secret/Security Posture). Accept this for round 1, or should a
   consolidated "Security posture" view be prioritized sooner?
5. **Notifications scope.** Round 1 shows Notifications as in-app only (external channels "Coming
   later"). Confirm that in-app-only is the intended round-1 scope.

## For Claude Code (architecture review)

- Confirm no route target / contract change is implied by this brief (expected: none — consistent
  with `frontend-implementation-boundary.md`).
- Confirm the `OperatorConsole` vs Approvals/DLQ resolution (separate pages under one group) matches
  the intended backend/page structure.
- Confirm the placeholder set (66D / 66C.4 / 66S) matches the actual pending contracts.

## For Codex (no action yet)

- No implementation until the Product Owner authorizes after Claude Code's review. When authorized,
  start with the single round-1 PR described in `codex-implementation-notes.md` §7.

## Verdict values (per `docs/process/operator-validation-standard.md`)

This is a design artifact, so the applicable Product-Owner responses are the design-readiness
equivalents. Please record one of:

```text
READY_FOR_CODE_REVIEW   — design accepted; forward to Claude Code architecture review
PARTIAL_WITH_GAPS       — accepted with noted gaps to address in a follow-up
NEEDS_ANOTHER_ROUND     — send back to Claude Design with required changes
```

(Final product acceptance of any *implemented* result remains a separate operator verdict —
`VISIBLE` / `NOT_VISIBLE` / `PARTIAL_WITH_GAPS` — given only after Codex builds and Claude Code
deploys to the test runtime.)

## Statement

Design specification only. No runtime code. No production action. No Codex implementation authorized
by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
