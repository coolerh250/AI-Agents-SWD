# Claude Code Review — Step 66UI.4-FE.1B Calm Safety Posture

Marker: `STEP66UI4_FE1B_REVIEW_VERIFY: PASS`

Reviewed by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`). Review scope: PR #7,
`frontend/66ui4-fe1b-calm-safety`, commit `6cf8efe`.

## Verdict

**PASS.** FE.1B fully respects its authorized scope, the safety mapping is conservative and
product-readable in every case tested, raw evidence remains accessible everywhere the calm summary
appears (including the compact global bar), and no forbidden capability was introduced or claimed.
Ready for Product Owner UI validation. Not merged. FE.1B does not authorize FE.1C or FE.1D.

## 1. Shared Context Preflight

- Latest main reviewed: `77ab4e0` (Step 66UI.4-FE.1A-MD — FE.1A merged and deployed/calibrated to
  test runtime).
- Skill files reviewed: `shared-context`, `stage-gate`, `security-governance`,
  `frontend-implementation`.
- Shared docs reviewed: `source/progress.md`, `docs/process/source-of-truth-policy.md`,
  `docs/process/context-guard-protocol.md`, `docs/process/stop-conditions.md`,
  `docs/design/66ui-source-of-truth-record.md`, Phase 1 design brief, visual-language spec,
  **calm-safety-posture-spec.md**, **engineering-field-reduction-map.md**,
  **product-microcopy-guide.md**, frontend-implementation-boundary.md, codex-readiness-boundary.md,
  fe1a-merge-record.md, step66ui4-fe1a-merged-main-test-deployment-record.md.
- Codex PR/branch reviewed: PR #7, `frontend/66ui4-fe1b-calm-safety`, commit `6cf8efe` (`gh pr view
  7`: OPEN, base `main`, 14 files changed, mergeable, +1078/-56).
- New information found: none contradicting the authorized scope; the calm safety posture spec and
  engineering-field reduction map are the two design docs this stage draws directly from, and both
  were confirmed present and unchanged on `main`.
- Conflicts found: none.
- How the new information affected this review: none — proceeded exactly per the FE.1B authorization
  boundary already established in `frontend-implementation-boundary.md` §2 and
  `codex-readiness-boundary.md` §1.

## 2. Scope confirmed

`git diff origin/main...origin/frontend/66ui4-fe1b-calm-safety --name-only` — 14 files, exactly 5
runtime files, all under `apps/admin-console/src/`:

```text
apps/admin-console/src/__tests__/CalmSafetyPosture.test.tsx   (new test)
apps/admin-console/src/components/CalmSafetyPosture.tsx        (new component)
apps/admin-console/src/components/SafetyStatusBar.tsx          (modified)
apps/admin-console/src/pages/SafetyCenter.tsx                   (modified)
apps/admin-console/src/styles.css                               (modified, +24/-9)
```

Remaining 9 files are this stage's own docs/verifier/test/progress artifacts. No `apps/orchestrator/`,
`services/`, `infra/`, `migrations/`, `database/`, `helm/`, `k8s/`, or `.github/workflows/` path
touched — confirmed both by direct diff inspection and by independently re-running Codex's own
`assert_scope()` check in `verify_step66ui4_fe1b_calm_safety.py`.

`apps/admin-console/src/api/operations.ts` is **not** in the diff — no API client contract change.
`apps/admin-console/src/pages/ExecutiveOverview.tsx` and `apps/admin-console/src/components/Nav.tsx`
/ `NavGroup.tsx` are **not** in the diff — no FE.1C Overview restructure, no FE.1D navigation polish.

### 22 required review checks

| # | Check | Result |
| --- | --- | --- |
| 1 | Existing `/operations/safety` data is used | PASS — `getSafety`/`getSafetySummary` calls unchanged |
| 2 | No API client contract change | PASS — `api/operations.ts` absent from diff |
| 3 | No backend/API/database/workflow/infra changes | PASS — diff confined to `apps/admin-console/src/**` + this stage's docs |
| 4 | No production/external action | PASS — no such code path added |
| 5 | No new safety endpoint | PASS |
| 6 | No new backend safety computation | PASS — all mapping logic lives in `CalmSafetyPosture.tsx` (frontend only) |
| 7 | Frontend safety mapping is presentation-only | PASS — `getCalmSafetyPosture()` only branches on already-fetched field values, never mutates or re-requests them |
| 8 | Raw safety evidence remains visible or accessible | PASS — the `Evidence / details` `<details>` block renders unconditionally, including in `compact` mode (explicitly asserted by the branch's own test `"renders compact mode without hiding technical details"`) |
| 9 | Unknown/missing data does not show fake safe status | PASS — falls to `"unavailable"` tone, never `"safe"`, when required fields are absent |
| 10 | Unsafe/attention states are not visually minimized | PASS — distinct amber `safety-posture-attention` badge + explicit "Attention needed" title, same visual weight as the safe state |
| 11 | Safe/off states are not shown as alarming red errors | PASS — safe uses `--success` (green), never `--danger` (red) |
| 12 | Safety wording does not overclaim autonomy or guarantee | PASS — wording matches `calm-safety-posture-spec.md` verbatim ("Safe — no automated or production actions will run"), a present-tense factual statement, not a permanent guarantee |
| 13 | No workflow dispatch/resume controls added | PASS — no dispatch/resume trigger of any kind; presentation only |
| 14 | No client-side-only RBAC introduced | PASS |
| 15 | No Delivery real UI | PASS |
| 16 | No Reminder/Expiry real UI | PASS |
| 17 | No Pipeline board or drag/drop | PASS |
| 18 | No new agent activity model | PASS |
| 19 | No FE.1C Overview attention-first restructure | PASS — `ExecutiveOverview.tsx` untouched |
| 20 | No FE.1D navigation polish outside safety surfaces | PASS — `Nav.tsx`/`NavGroup.tsx` untouched |
| 21 | Local-only `.tools/` not part of PR | PASS — confirmed via `git diff --name-only` grep |
| 22 | Unrelated `docs/product/platform-progress-admin-console-proposal.md` not part of PR | PASS — confirmed via `git diff --name-only` grep |

## 3. Safety mapping review

Read `CalmSafetyPosture.tsx` in full (`getCalmSafetyPosture`, `factFromBooleanGroup`,
`productionFact`, `approvalFact`). Field groups:

```text
AUTOMATION_FIELDS = dispatch_enabled, resume_dispatch_enabled, task_api_workflow_dispatch_enabled,
                    task_workroom_resume_dispatch_enabled
EXTERNAL_FIELDS   = github_external_write_enabled, discord_external_send_enabled,
                    llm_external_call_enabled
PRODUCTION_COUNT_FIELDS = production_executed_true_count, workflow_production_executed_true_count
```

| # | Validation | Result |
| --- | --- | --- |
| 1 | If `production_executed_true_count` > 0, UI must not say "No production actions have run." | PASS — `productionFact()` only returns that copy when **both** count fields are strictly `0` (`allNumbers(..., 0)`); any positive value on either field forces `"Production actions are reported"` |
| 2 | If `dispatch_enabled` is true, UI must not say "Automated actions off." | PASS — `factFromBooleanGroup` requires **all** automation fields strictly `false` to show `"Off"`; any `true` forces `"On"` |
| 3 | If `resume_dispatch_enabled` is true, UI must not say "Workflow resume off." | PASS — folded into the same automation group, same guarantee |
| 4 | If any external field is true, UI must not say "External actions are disabled." | PASS — same conservative all-false-required logic for `EXTERNAL_FIELDS` |
| 5 | If data is missing, UI uses "not reported"/unavailable language | PASS — `boolState`/`numberState` return `null` for missing/non-boolean/non-number values, which fails both the "all false" and "any true" branches and falls through to `"not reported"`; overall tone falls to `"unavailable"` unless a real risk signal is present |
| 6 | Raw evidence still shows the underlying values | PASS — `SAFETY_EVIDENCE_FIELDS` (14 fields, a superset of the required 12) always renders via `formatSafetyValue`, independent of tone or compact mode |
| 7 | Summary status is derived conservatively | PASS, and stronger than required — the branch adds `resultWarns` (the raw `/operations/safety` `"result"` field disagreeing with `"safe"` also forces `"attention"`), so the frontend defers to the backend's own overall verdict rather than only re-deriving it from the individual flags Codex knows about today |

**On the open question Codex raised in its handoff** ("whether `result !== 'safe'` should keep
forcing the attention state when all individual safety flags are safe"): yes, this should be kept.
Trusting the backend's own aggregate `result` field as an additional, independent check is a
defense-in-depth choice — if the backend later adds a risk signal the frontend's field list doesn't
yet know about, this fallback still surfaces it as "attention" rather than silently reporting "safe"
on stale logic. This is consistent with, and a reasonable strengthening of, the "no fake safe status"
requirement — not a scope violation, since it reads an existing field already returned by
`/operations/safety` and does not add a new one.

Field-name note: the review checklist's illustrative field names
(`workflow_dispatch_enabled`/`workflow_resume_enabled`/`external_actions_enabled`) differ slightly
from the actual server field names (`dispatch_enabled`/`resume_dispatch_enabled`/three discrete
`*_external_*_enabled` flags) — verified against the live `/operations/safety` response recorded in
Step 66UI.4-FE.1A-MD and against `SAFETY_EVIDENCE_FIELDS` in the component itself; the actual fields
are what was checked above.

## 4. Implementation quality (UX / frontend)

| # | Item | Assessment |
| --- | --- | --- |
| 1 | Calm safety tone | Matches spec's reassurance-first language verbatim; no jargon in the primary summary line |
| 2 | Product-readable summary clarity | Clear — one badge + one sentence, five supporting facts in plain language |
| 3 | Evidence/details accessibility | Present on every page via the compact global bar and in full on Safety Center; keyboard-focusable `<details>`/`<summary>` (native disclosure semantics, satisfies the spec's accessibility rule) |
| 4 | Unknown state clarity | "Safety status unavailable - check system evidence." plus per-field "not reported" — honest, not alarming, not falsely reassuring |
| 5 | Risk/attention visual treatment | Amber badge, distinct from safe; not minimized |
| 6 | Safe/off visual treatment | Green badge, calm — not styled as a red/danger error |
| 7 | Compatibility with FE.1A visual tokens | Reuses `--space-*`, `--radius-sm`, `--line-subtle`, `--surface-quiet`, `--muted-strong` consistently; no new palette introduced |
| 8 | Responsiveness risk | Low — `calm-safety-facts` uses `repeat(auto-fit, minmax(220px, 1fr))`; the evidence table collapses to a single column under the existing `@media (max-width: 820px)` breakpoint (added by this PR) |
| 9 | Accessibility / contrast risk | Independently measured: badge text colors against the page background (`#0f1419`) — success `9.86:1`, warning `10.39:1`, neutral `11.39:1` — all clear WCAG AAA (7:1) for normal text; these are the same token values already used by the pre-existing `.b-ok`/`.b-warn`/`.b-neutral` classes, not new colors |
| 10 | Safety Center usability for operators/security reviewers | Improved, not reduced — the calm panel is additive; the full raw `KeyValueTable` safety summary directly below it is unchanged, so a security reviewer retains one-click access to the complete raw payload alongside the new plain-language framing |

## 5. Independent re-verification

Performed in a disposable `git worktree` (`git worktree add ... origin/frontend/66ui4-fe1b-calm-safety
--detach`), removed after, plus a `node_modules` filesystem junction (package.json/lock confirmed
byte-identical to `main` first) to avoid a slow reinstall:

| Command | Result |
| --- | --- |
| `python scripts/verify_step66ui4_fe1b_calm_safety.py` | PASS (reproduced) |
| `pytest tests/test_step66ui4_fe1b_calm_safety.py` | 1 passed (reproduced) |
| `npm test` (full suite) | 15 files / 110 tests passed (reproduced) |
| `npm run build` | passed — `index-D3ONvmz8.js` / `index-DcSljMgU.css` |
| `npm run typecheck` | passed, no output (clean) |

All results match Codex's own test report exactly. Frontend tests, build, and typecheck were
independently rerun (not merely reviewed as claims).

## 6. Known gaps (non-blocking)

```text
- The review checklist's illustrative safety field names differ from the server's actual field
  names; documented above with the mapping used for verification.
- Codex's own verifier's scope check (assert_scope) is a no-op when run on a clean checkout with no
  local diff, same class of gap noted at FE.1A-R; this review's own git diff origin/main... check
  already confirms real scope independently.
- Safety Center's legacy raw KeyValueTable summary remains alongside the new calm panel (not
  collapsed further) — Codex explicitly flagged this as an open question for a future stage; no
  safety concern, purely a future decluttering opportunity for FE.1D or later.
```

No blocking gap. FE.1B is ready for Product Owner UI validation.

## Statement

Review only. No runtime code changed by this document. No backend/API/database/workflow change. No
production/external action. FE.1C/FE.1D remain unauthorized. PR #7 not merged.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
