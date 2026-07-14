# Product Owner Review Checklist — DESIGN-66UI.4 Phase 1

> Owner: Claude Design. For Zachary (Product Owner) to accept this Phase 1 brief for Claude Code
> architecture review, then authorize Codex. Acceptance here ≠ authorization to implement.

## Acceptance checklist

| # | Criterion | Where addressed | ☐ |
| --- | --- | --- | --- |
| 1 | Global product visual language is concrete (tokens, density, type, color) | `visual-language-spec.md` | ☐ |
| 2 | Calm safety posture keeps server values but reads as reassurance | `calm-safety-posture-spec.md` | ☐ |
| 3 | Overview leads with "what needs you," metrics demoted | `overview-dashboard-spec.md` | ☐ |
| 4 | Navigation polish changes visuals only — no IA/route change | `navigation-visual-polish-spec.md` | ☐ |
| 5 | Engineering-field reduction is specific (field-by-field) | `engineering-field-reduction-map.md` | ☐ |
| 6 | Product microcopy is concrete (before/after strings) | `product-microcopy-guide.md` | ☐ |
| 7 | Safety signals relocated, never removed; off-states read as calm not alarm | specs 2, 5, 6 | ☐ |
| 8 | No fabricated data; 66D/66C.4 counts stay honest placeholders | `overview-dashboard-spec.md`, `codex-implementation-notes.md` | ☐ |
| 9 | Existing dark palette refined, not replaced (no theme change in Phase 1) | `visual-language-spec.md` | ☐ |
| 10 | Ready for Codex to build as a frontend-only, revertible change | `codex-implementation-notes.md` | ☐ |

## Open questions for the Product Owner

1. **Muted-text contrast.** Phase 1 proposes nudging meaning-bearing muted text lighter/larger for
   AA contrast on the dark ground. Accept, or keep exact current muted tone?
2. **Agent identity now or later.** The Overview team-activity strip introduces agent identity
   chips. Include the (read-only, server-sourced) team-activity strip in Phase 1, or defer it to the
   Workroom phase (Phase 2)?
3. **PR shape.** One cohesive Phase 1 PR, or the 4-step sequence in `codex-implementation-notes.md`
   §5?

## For Claude Code (architecture review)

- Confirm no route/contract change (expected: none — existing endpoints only).
- Confirm the calm safety posture reads the same server source and does not infer/hardcode values.
- Confirm the honest-placeholder rule for 66D/66C.4-gated Overview counts is sufficient.

## For Codex

- No implementation until Claude Code review + explicit Product Owner authorization. Then build per
  `codex-implementation-notes.md`.

## Verdict values (design-readiness)

```text
READY_FOR_CODE_REVIEW   — accept; forward to Claude Code architecture review
PARTIAL_WITH_GAPS       — accept with noted gaps
NEEDS_ANOTHER_ROUND     — send back with required changes
```

(Product acceptance of the *implemented* Phase 1 remains a separate operator verdict —
`VISIBLE` / `NOT_VISIBLE` / `PARTIAL_WITH_GAPS` — after Codex builds and Claude Code deploys to the
test runtime.)

## Statement

Design specification only. No runtime code. No production action. No Codex implementation authorized
by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
