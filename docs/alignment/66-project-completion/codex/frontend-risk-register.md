# Frontend Risk Register

Step: 66ALIGN.1-CODEX

## Alignment Result

Result: `ALIGNED_WITH_GAPS`

The frontend direction is aligned with the canonical milestone order, but production completion has
contract and state-management gaps. The main risk is not visual polish; it is implementing real
Delivery, Action Center, orchestration control, or production rollout UI ahead of backend contracts.

## Risks

| ID | Risk | Milestone | Severity | Mitigation |
| --- | --- | --- | --- | --- |
| FE-R1 | Frontend builds Delivery Inbox/Detail before Step 66D freezes list/detail/decision contracts. | M2 | High | Contract-first fixtures and Claude Code boundary before UI. |
| FE-R2 | Action Center fakes notifications or action counts from partial task data. | M4 | High | Unified action item backend contract; honest placeholders until then. |
| FE-R3 | Agent activity is interpreted as live orchestration capability. | M3 | High | Read-only display only until agent identity/status/control contracts exist. |
| FE-R4 | `AsyncView` is reused for multi-source mutable workflows, causing inconsistent refresh/error states. | M4/M5 | Medium-high | Introduce shared query/mutation pattern before Action Center. |
| FE-R5 | FE.1D-S2 consumes review time while not unlocking core flow. | M1/M2 | Medium | Fold useful pieces into functional slices; pause cosmetic-only work. |
| FE-R6 | Client-side role banners are mistaken for production RBAC. | M7 | High | Replace test-role simulation with production auth/session contract; document server authority. |
| FE-R7 | Operator controlled actions are extended without capability flags or audit contract. | M2/M4/M6 | High | Named methods only, CSRF/idempotency, server capability flags, audit response fixtures. |
| FE-R8 | Raw evidence tables stay too technical for operators. | M2/M6 | Medium | Add product label maps only when page-specific contract exists; keep technical details reachable. |
| FE-R9 | SPA deep-link fallback is patched in frontend or hidden by URL tricks. | M0/M6 | Medium | Treat as backend/platform gap; no frontend workaround as "fix." |
| FE-R10 | Accessibility is deferred until late production rollout. | M6/M7 | Medium-high | Add milestone accessibility requirements and consider automated a11y checks. |
| FE-R11 | Loose `Record<string, unknown>` operations data masks backend changes. | M6 | Medium | Add typed contract fixtures for production-relevant pages. |
| FE-R12 | Notifications/channels imply external sends without authorization. | M4 | High | Read-only channel status first; external action requires explicit Product Owner authorization. |

## Cosmetic Work To Defer

- Optional Platform Ops visual sub-headers.
- Broad evidence-table label cleanup without explicit mapping.
- Standalone microcopy-only PRs that do not support M1/M2/M4 functional clarity.
- `delivery_package_ready_for_admin_console` rename before Step 66D.
- `+ Create task` rename unless Product Owner reverses the decision.

## Work That Can Merge Naturally With Core Delivery

- Status labels and relative time in TaskList while improving M1 task triage.
- TaskDetail technical details disclosure while improving M1/M2 task-delivery detail.
- Placeholder wording when replacing placeholders with real M2/M4 surfaces.
- Safety wording consistency while hardening M6 safety/readiness pages.

## Conflicts With Canonical Milestone Plan

No direct conflict found. The current repo state is compatible with the canonical order if:

1. FE.1D-S2 remains non-critical.
2. M2 waits for Step 66D.
3. M4 waits for a unified action/notification contract.
4. SPA deep-link fallback remains tracked as backend/platform work.

## Open Gaps

- FE.1D boundary docs are not merged to main, although FE.1D-S1 implementation/review/validation/merge
  records are on main.
- No formal frontend route/API contract inventory exists yet.
- No shared frontend data-fetching/mutation state pattern exists for Action Center.
- No production auth/settings frontend contract exists.
- No automated accessibility suite exists.
