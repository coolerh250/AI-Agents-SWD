# Technical Critical Path — Step 66ALIGN.1-CC

> **Analysis and documentation only. No implementation, merge, deployment, or runtime modification
> performed by this document.**

## Critical path (confirmed, unchanged from the canonical order)

```text
M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7
```

## Current position on the critical path

```text
M0: effectively satisfied (one non-blocking hygiene item outstanding -- see current-state-
    assessment.md's reconciliation plan).
M1: PARTIALLY complete. 66B and 66C are done and merged/deployed. 66C.4 (Reminder/Expiry) is the
    single remaining item and is READY_TO_START -- it is the next item ON the critical path.
M2 through M7: not started.
```

**This project's most recent completed work (FE.1D-S1 Navigation Polish, and the FE.1D design/
technical-readiness/boundary chain still awaiting a merge decision) is entirely OFF the critical
path.** It improves the existing Admin Console's presentation layer but does not unblock M1's
remaining item (66C.4) or any milestone after it. This is the single most important finding of this
alignment analysis: **recent execution capacity was spent on FE.1D-S1, which does not advance the
critical path**, while 66C.4 — the actual next critical-path item — has been READY_TO_START without
being picked up.

## Why 66C.4 is the correct next critical-path stage

```text
1. It is the only remaining item in M1 -- completing it closes the milestone.
2. It has no unresolved data-model question: clarification_expired already exists in TASK_STATUSES
   (apps/admin-console/src/tasks/taskTypes.ts), and the 24h/72h timeout was already operator-
   decided (Q2, Step 66A.3). There is no design ambiguity blocking it.
3. It is backend-light: most likely a scheduled job (consistent with the existing retry-scheduler
   service's pattern) plus a notification-worker hook plus one real frontend page replacing
   today's PlaceholderPage at /clarification-reminders.
4. Unlike M2 (66D), it requires no new delivery data model, so it carries materially lower design
   risk and can start immediately without a data-model freeze decision first.
```

## Why FE.1D-S2 and further cosmetic work should not be prioritized ahead of 66C.4

```text
FE.1D-S2 (microcopy/field-label cleanup) improves labels on pages that already exist and already
  work. It does not unblock any milestone. Its own boundary/slicing-plan documents already say
  this explicitly (docs/contracts/66ui4-fe1d-navigation-microcopy/implementation-slicing-plan.md).
Continuing cosmetic polish while 66C.4/66D remain unstarted extends the time-to-value of the
  entire M1-M7 chain without a corresponding increase in what the product can actually do. This is
  a direct answer to this stage's own required question ("是否應在 FE.1D-S1 後暫停 cosmetic work?")
  -- see alignment-statement.md for the full answer.
```

## Non-critical-path work that may run in parallel without risk

```text
FE.1D-S2 (if the Product Owner wants it) -- touches only Admin Console display strings, zero
  overlap with 66C.4/66D backend or data-model work, zero shared file risk (different files,
  different services).
The three unmerged FE.1D branches (design/technical-readiness/boundary) -- a merge decision on
  these is a housekeeping action, not a critical-path dependency; it can happen whenever the
  Product Owner wants, without blocking 66C.4.
Any further governance/production-readiness DRY-RUN rehearsal work (extending the Stage 60-63A
  kind/ArgoCD sandbox exercises) -- useful preparation for M6, and since it is explicitly
  non-production and reversible, it carries no risk of interfering with M1/M2 backend work. It
  should not, however, be mistaken for M6 itself (see risk-register.md).
```

## Statement

Analysis and documentation only. No implementation, merge, deployment, or runtime modification
performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
