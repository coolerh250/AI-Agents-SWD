# Frontend Test Strategy

Step: 66ALIGN.1-CODEX

## Current Test Baseline

The Admin Console currently uses Vitest and React Testing Library. `package.json` provides:

```text
npm test
npm run build
npm run typecheck
```

There is no frontend lint script.

Existing coverage includes:

- API GET-only guard.
- Task API guard.
- Workroom plain-text, clarification, RBAC, and audit evidence.
- Navigation grouping, route preservation, placeholder safety, and FE.1D-S1 badges.
- Overview attention-first behavior and honest placeholders.
- Calm safety posture.
- Operator action client guard and CSRF/idempotency behavior.
- Product UI formal pages and demo evidence.
- Redaction and status formatting.

## Milestone Test Strategy

| Milestone | Required frontend tests |
| --- | --- |
| M0 | Static checks for route/API inventory docs if tooling is added; no runtime tests for docs-only work. |
| M1 | Task create/list/detail/workroom flows; message/clarification validation; RBAC errors; no HTML rendering; no dispatch/resume; audit evidence restricted/allowed states. |
| M2 | Delivery inbox/detail fixtures; acceptance/request-changes/reject/add-note capability flags; reason validation; CSRF/idempotency; audit trail refresh; no production/external action. |
| M3 | Agent execution display from observed data; unknown status fallback; no fake controls; server-filtered role visibility; execution detail drawer if added. |
| M4 | Unified action item fixtures; restricted action visibility; read/unread/ack/resolve/snooze only after contract; channel status without external send; shared state refresh behavior. |
| M5 | Scripted pilot UI scenario over mocked contracts first, then test-runtime validation checklist; no production/external action; evidence package completeness. |
| M6 | Read-only guard, no secret leakage, typed operations fixtures, safety posture evidence, stale data, accessibility checks for dense evidence tables. |
| M7 | Production auth/session behavior, settings persistence, onboarding flows, support/runbook navigation, role-specific smoke tests. |

## Cross-Cutting Required Tests

- No `dangerouslySetInnerHTML`.
- No markdown-to-HTML for user/agent content.
- No raw audit body rendering.
- No local/session storage of credentials or tokens.
- Test role local storage remains non-secret only until production auth replaces it.
- Server-side RBAC is the authority; UI tests must not claim client-side security.
- Placeholder pages never render fake controls.
- SPA deep-link fallback remains documented as backend/platform gap unless a backend stage fixes it.
- `+ Create task` remains unchanged unless Product Owner reverses the current decision.
- `delivery_package_ready_for_admin_console` remains unchanged until Step 66D decides it.

## Preview And PO Validation Strategy

| Milestone | Preview strategy |
| --- | --- |
| M0 | Document review only. |
| M1 | Test-runtime walkthrough with created task, Workroom message, clarification creation/answer, audit evidence, role restriction. |
| M2 | Test-runtime delivery package scenario with known delivery item IDs and reviewer/operator/security roles. |
| M3 | Test-runtime agent execution sample: recent activity, unknown statuses, no invented controls. |
| M4 | Read-only action center preview first; mutation preview only after audit-capable backend contract. |
| M5 | Controlled pilot script with checkpoints and Product Owner validation record. |
| M6 | Security/compliance validation over evidence, safety, readiness, access restrictions. |
| M7 | Target-role adoption validation with operators/admins and production-like auth. |

## Verification Commands For Runtime Frontend PRs

Runtime frontend PRs should run:

```text
npm test
npm run build
npm run typecheck
git diff --check
secret scan if available
```

Documentation-only alignment PRs should at minimum run:

```text
git diff --check
git status --short
secret/local artifact scan before commit
```

## Test Gaps To Address Before Production

1. No automated accessibility runner is configured.
2. No frontend lint script exists.
3. Many operations pages rely on loose `Record<string, unknown>` fixtures.
4. No Playwright/browser smoke suite is established for production candidate builds.
5. No shared fixture catalog maps backend contract versions to frontend tests.
6. Action Center and Delivery Review need contract-first test suites before implementation.
