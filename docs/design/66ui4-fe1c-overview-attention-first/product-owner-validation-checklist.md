# Product Owner Validation Checklist — DESIGN-66UI.4-FE.1C

> Owner: Claude Design. For Zachary (Product Owner) to accept this FE.1C brief for Claude Code
> review, and later to validate the *implemented* Overview. Acceptance of the brief ≠ authorization
> to implement.

## Design-brief acceptance (now)

| # | Criterion | Where | ☐ |
| --- | --- | --- | --- |
| 1 | Overview reads as an AI Team Command Center, not a metrics dump | `information-architecture.md`, `layout-wireframe.md` | ☐ |
| 2 | "Needs your attention" leads the page | IA §B | ☐ |
| 3 | Every dynamic value maps to existing data | `existing-data-mapping.md` | ☐ |
| 4 | No new backend/API/DB/workflow requested | brief §"existing-data-only", `existing-data-mapping.md` | ☐ |
| 5 | 66D / 66C.4 items are honest placeholders (no fake numbers/controls) | `placeholder-and-empty-state-strategy.md` | ☐ |
| 6 | FE.1B safety posture reused, not duplicated | IA §E, `existing-data-mapping.md` | ☐ |
| 7 | Existing 12 metrics cards preserved but demoted | IA §F | ☐ |
| 8 | Microcopy is product-readable, reassurance-first | `microcopy-guide.md` | ☐ |
| 9 | No IA/route change; FE.1A tokens unchanged | brief §"does NOT do" | ☐ |
| 10 | Codex remains unauthorized pending review + explicit go-ahead | `codex-implementation-boundary.md` | ☐ |

## Later — implemented-UI validation (after Codex builds + Claude Code deploys to test runtime)

Walk the deployed Overview and confirm:

```text
- The page opens with "what needs me," not a metrics grid.
- Decisions-waiting / Blocked reflect real tasks (or a calm "all caught up" when none).
- AI team activity shows real recent agent runs (or "No recent agent runs").
- Current work shows recent tasks with product-readable status + relative time.
- System posture shows the calm "Safe" summary and links to Safety (no duplicated detail).
- Platform & delivery metrics still present, demoted.
- Delivery Review / Reminder / Notifications / Pipeline show honest placeholders with
  "No workflow action available from this screen" and no controls.
- No fabricated numbers anywhere; zero states read as calm "all clear."
```

Operator verdict values (implemented UI): `VISIBLE` / `NOT_VISIBLE` / `PARTIAL_WITH_GAPS`.

## Design-readiness verdict (this brief)

```text
READY_FOR_CODE_REVIEW   — accept; forward to Claude Code architecture review
PARTIAL_WITH_GAPS       — accept with noted gaps
NEEDS_ANOTHER_ROUND     — send back with required changes
```

## Statement

Design specification only. No runtime code. No production action. No Codex implementation authorized
by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
