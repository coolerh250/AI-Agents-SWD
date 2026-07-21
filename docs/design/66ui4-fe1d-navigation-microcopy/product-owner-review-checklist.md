# Product Owner Review Checklist — Step 66UI.4-FE.1D-DESIGN

> Owner: Claude Design. For Zachary to accept this FE.1D design for Claude Code technical-readiness
> review, then authorize Codex. Acceptance of the design ≠ authorization to implement.

## Acceptance checklist

| # | Criterion | Where | ☐ |
| --- | --- | --- | --- |
| 1 | Navigation polish is label/badge/subtitle only — no route or IA change | `navigation-polish-spec.md` | ☐ |
| 2 | Placeholder nav items get a visible "Soon"/stage marker | `navigation-polish-spec.md` §2 | ☐ |
| 3 | Microcopy is product-language, consistent with shipped FE.1B/FE.1C | `microcopy-guide.md` | ☐ |
| 4 | Field label rename map changes display only; enum/API values unchanged | `field-label-cleanup-map.md` | ☐ |
| 5 | Safety field labels reuse FE.1B.1 wording — NOT re-renamed | `field-label-cleanup-map.md` note | ☐ |
| 6 | Engineering-field reduction is categorized A/B/C/D; D excluded from FE.1D | `engineering-field-exposure-reduction.md` | ☐ |
| 7 | Platform Ops density polish is minimal (labels/markers/optional sub-headers), not a reorg | `platform-ops-density-spec.md` | ☐ |
| 8 | Placeholder + empty-state wording standardized to one pattern | `microcopy-guide.md` | ☐ |
| 9 | Safety wording is micro-polish only; safety logic untouched | `microcopy-guide.md` safety section | ☐ |
| 10 | SPA deep-link fallback is explicitly OUT of FE.1D (backend, later) | `design-brief.md`, `codex-implementation-notes.md` | ☐ |
| 11 | Codex remains unauthorized until Claude Code review + explicit go-ahead | `codex-implementation-notes.md` | ☐ |

## Decisions the Product Owner may want to weigh in on

1. **"Ready to publish" rename** for `delivery_package_ready_for_admin_console` — is that the
   intended meaning? (Marked [confirm].)
2. **Notifications placeholder wording** — accept a "Planned" phrasing instead of "Requires Step
   future notifications stage."?
3. **Platform Ops sub-headers** — include the optional visual sub-grouping (#4 in the density spec),
   or keep FE.1D to labels + markers only?
4. **"New task" vs "Create task"** label preference.

## For Claude Code (technical-readiness review)

- Confirm every proposed change is frontend-only (display strings, badges, subtitle text, relative-
  time formatting, a shared status-label module, wrapping an existing raw dump in a disclosure) with
  no data/API/route change.
- Confirm the authoritative `TASK_STATUSES` enum list so the completed status-label map is exhaustive.
- Rule on the `[confirm with Claude Code]` items (raw-ID pages, hash relabels, Notifications
  placeholder copy mechanism, Task Detail raw-dump disclosure).
- Confirm no proposal re-opens FE.1B/FE.1B.1 safety logic or the SPA deep-link (backend) gap.

## For Codex

- No implementation until Claude Code review passes AND the Product Owner explicitly authorizes.
  Then implement per `codex-implementation-notes.md`, frontend-only.

## Design-readiness verdict

```text
READY_FOR_CODE_REVIEW   — accept; forward to Claude Code technical-readiness review
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
