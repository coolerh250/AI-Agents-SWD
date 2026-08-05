# Step 66D-DESIGN — Frontend Handoff, Terminology and Acceptance Criteria (FROZEN)

> **Design specification and handoff only. No frontend source created or modified. No component
> exists. Codex is NOT authorized. `production_executed_true_count: 0`.**

```text
CANONICAL_BASELINE: main 9c5210d190b82b76575ba8d456b5d2005c2867d2
COMPONENT CANDIDATES: 22 (measured: manifest component_candidates length)
ACCEPTANCE CRITERIA:  18 (measured: manifest acceptance_criteria length)
```

## 1. Canonical UI terminology (frozen)

| Term | Meaning in the UI | Must never be shown as |
| --- | --- | --- |
| **Delivery Submission** | the versioned human-acceptance aggregate a PO accepts/rejects | the legacy DeliveryPackage; a Task |
| **Delivery Review Task** | the human review anchor and queue entry (`delivery_review_task_id`) | the execution source of truth |
| **Review Gate Action** | one of exactly six workflow moves | a final decision; an approval |
| **Product Owner Decision** | one of exactly three immutable final decisions | a review action; a status; an approval grant |
| **Acceptance Follow-up** | a non-blocking item raised by `ACCEPTED_WITH_FOLLOW_UP` | a blocker; a defect ticket that gates acceptance |
| **Effective Decision** | the current non-superseded `ProductOwnerDecision` | the projected status |
| **Superseded Decision** | a historical decision replaced via `supersedes_decision_id` | deleted or edited history |
| **QA Rerun** | bounded re-verification, no content change | a content revision |
| **Request Changes** | content revision requested; new version required | a rejection; a QA rerun |
| **Evidence Health** | COMPLETE/PARTIAL/MISSING/STALE/INACCESSIBLE/UNKNOWN | a pass/fail verdict |
| **External AI Partner** | Claude Code / Codex / Claude Design (`ai_partner`) | a runtime agent |
| **Runtime Agent** | an implemented agent service (`runtime_agent`) | an external AI partner |

Forbidden conflations (each is a defect):

```text
Approval = Product Owner Decision          Task = Agent execution
DeliveryPackage = DeliverySubmission       Accept action = accepted status = PO decision
Partner = runtime agent                    Archived = success
Projection = authoritative decision record UNKNOWN = PASS
```

Copy rules: plain language · actionable · non-technical where possible · faithful to canonical error
semantics (see the state/error matrix §3). Never expose stack traces, raw exceptions, database
detail, secrets, tokens or internal credential references.

## 2. Component responsibility handoff (candidates — names are suggestions, nothing exists)

For each: responsibility · inputs · display states · user actions · backend contract dependency ·
existing reuse candidate · a11y requirement · responsive behavior. All backend dependencies are
**NOT IMPLEMENTED**.

| # | Candidate | Responsibility | Key inputs | States | Actions | Backend dependency | Reuse candidate | A11y | Responsive |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `UnifiedControlCenterPage` | project-level container + section anchors | `project_id`, read model | loading/empty/partial/stale/error/inaccessible | navigate, refresh | `project_delivery_control_center` | `AsyncView`, `Layout` | h1, landmarks, skip link | stacks at 1024 |
| 2 | `ProjectContextHeader` | goal/project/stage/health/freshness/env | read-model header slice | all seven | refresh | read model | existing page header patterns | h1 + status text | wraps |
| 3 | `AttentionQueue` | prioritized blocking/attention items | attention items | all seven | deep-link | read model | `EmptyState`, `StatusBadge` | list semantics, severity text | full list kept |
| 4 | `LifecycleProgress` | nine stages × seven states | lifecycle slice | all seven | none | read model | `StatusBadge` | text+icon per stage | horizontal scroll w/ labels |
| 5 | `DeliveryAcceptanceSummary` | submission/review/decision summary + CTA | submission + review + effective decision | all seven | deep-link to review | submission/review/decision APIs | `DataCard`, `StatusBadge` | projection labelled | stacks |
| 6 | `ExecutionSummary` | workflow/run + agent vs partner activity | execution slice | all seven | deep-link | read model + existing execution sources | `KeyValueTable` | actor type in text | stacks |
| 7 | `EvidenceHealthPanel` | seven categories × six states | evidence slice | all seven | deep-link | read model | `StatusBadge` | UNKNOWN never green | chips wrap |
| 8 | `CostExternalActionSummary` | cost/external/production counters | cost slice | all seven | deep-link | read model | `DataCard` | read-only text | stacks |
| 9 | `SafetySummary` | posture summary + deep link | safety slice | all seven | deep-link | existing `/operations/safety` + read model | **`CalmSafetyPosture` (exists)** | server-derived text | compact |
| 10 | `ActivityTimeline` | unified timeline, kinds distinguished | timeline slice | all seven | deep-link | read model | existing evidence list patterns | kind in text | stacks |
| 11 | `DeliveryInboxPage` | cross-project queue container | filters, sort, cursor | all seven | filter/sort/navigate | review-task queue read model | `AsyncView` | h1 + table caption | table→cards |
| 12 | `DeliveryInboxTable` | rows + CTA | queue rows | all seven | navigate | queue read model | existing table patterns | aria-sort, scoped headers | column reduction |
| 13 | `DeliveryReviewPage` | submission review workspace container | `delivery_submission_id` | all seven | actions (FE2) | submission/action/decision APIs | `AsyncView` | h1, landmarks | stacked panels |
| 14 | `RequirementTraceabilityPanel` | nine-link chain + criterion results | traceability payload | all seven | filter, expand, deep-link | `GET /traceability` | `EvidenceTable` | table semantics | scrolls |
| 15 | `ArtifactEvidencePanel` | nine evidence categories + provenance | evidence payload | all seven | expand, deep-link | `GET /evidence` | `EvidenceTable`, `JsonPanel` (redacted) | redaction enforced | stacks |
| 16 | `ReviewGateActionPanel` | exactly six actions + availability | submission status, capability, rerun count | available/disabled/not-authorized/not-applicable/blocked | choose action | `POST /review-actions` | new | separate region + reasons in text | stacks |
| 17 | `ProductOwnerDecisionPanel` | exactly three decisions + effective/history | decision history | all seven | record decision | `POST /po-decisions` | new | separate region, projection labelled | stacks |
| 18 | `AcceptanceFollowUpPanel` | non-blocking follow-ups + blocking guard | follow-ups | all seven | add/edit | follow-up APIs | new | blocking reason in text | stacks |
| 19 | `FreshnessIndicator` | `as_of` / fresh / stale / unknown + refresh | freshness meta | fresh/stale/unknown/refreshing | refresh | read model `as_of`/`is_stale` | new (small) | live-region announce | inline |
| 20 | `DeepLinkCard` | summary + validated deep link + disabled reason | summary + target | available/disabled/missing-route | navigate | per-target route | `DataCard` | disabled reason in text | grid→stack |
| 21 | `ConflictRecoveryDialog` | canonical 409/422 recovery | error code + before/after | conflict variants | reload, discard, re-confirm | canonical error contract | new (modal pattern) | focus trap, assertive announce | full-width on tablet |
| 22 | `UnsupportedWriteNotice` | small-mobile explicit write-unsupported message | breakpoint | shown/hidden | none | none | new (small) | visible text, not a disabled control | < 768 only |

Existing components confirmed present for reuse (measured: 16 files in
`apps/admin-console/src/components/`): `AsyncView`, `DataCard`, `EmptyState`, `ErrorState`,
`EvidenceTable`, `JsonPanel`, `KeyValueTable`, `Layout`, `LoadingState`, `Nav`, `NavGroup`,
`PlaceholderPanel`, `SafetyBadge`, `SafetyStatusBar`, `StatusBadge`, `CalmSafetyPosture`.

## 3. Implementation slice mapping (canonical ARCH1 slices; none authorized)

| Slice | Canonical scope (ARCH1 §11) | Design package input | Authorization |
| --- | --- | --- | --- |
| `Step 66D-BE1` | persistence/domain models + migrations | domain refs in IA + interactions | NOT AUTHORIZED |
| `Step 66D-BE2` | DeliverySubmission + ReviewTask APIs | inbox spec, review context/summary | NOT AUTHORIZED |
| `Step 66D-BE3` | ReviewAction, PO Decision, follow-up APIs | interactions §2–§5, matrix §3 | NOT AUTHORIZED |
| `Step 66D-BE4` | events, outbox, audit, unified read model | IA §3, matrix §5 (freshness) | NOT AUTHORIZED |
| `Step 66D-FE1` | Delivery Inbox / Delivery Review **observation** surfaces | inbox spec, IA, route map, states | NOT AUTHORIZED |
| `Step 66D-FE2` | review actions, PO decisions, follow-ups | interactions spec, wireframes WF-05..WF-10 | NOT AUTHORIZED |
| `Step 66D-QA` | combined contract/runtime/UI/security/a11y check | acceptance criteria §4 + a11y spec | NOT AUTHORIZED |

ARCH1 slice names match the prompt's mapping; no renaming was required. FE1 additionally requires
replacing the `PlaceholderPage` element on the existing `/delivery-inbox` route and adding the two
absent routes — **a Codex action under a future authorization, not performed here.**

## 4. Design acceptance criteria (observable / testable)

| ID | Criterion |
| --- | --- |
| AC-01 | From `/projects/:projectId/control-center` alone, a PO can state the project's current stage, whether anything blocks it, and what the next step is, without visiting another route. |
| AC-02 | Every blocking attention item is visible within the first screen or one scroll at 1440px, 1280px and 1024px. |
| AC-03 | The Review Gate Action Panel and the Product Owner Decision Panel are separate regions with distinct headings and are never nested one inside the other. |
| AC-04 | The ACCEPT confirmation displays both the review action and the final decision, and states that they are two records written together. |
| AC-05 | With any follow-up item marked `blocking = true`, `ACCEPTED_WITH_FOLLOW_UP` cannot be submitted, no auto-conversion occurs, and the UI directs the user to `REQUEST_CHANGES`. |
| AC-06 | The QA rerun quota rendered in the UI equals the backend-authoritative value; no client-side counter is used to derive it. |
| AC-07 | With `1 of 1` reruns used, no submittable `RERUN_QA` control is rendered, and the disabled copy names `REQUEST_CHANGES`, `ESCALATE`, `REJECT`. |
| AC-08 | With status `EXPIRED`, `ACCEPT` and `REJECT` are disabled and no final decision can be recorded. |
| AC-09 | When `is_stale` is true, a stale indicator, `as_of`, a refresh affordance, and a note of which decisions may be unsafe are all shown. |
| AC-10 | A missing data source renders `UNKNOWN` or `MISSING` and never renders as PASS, healthy, zero or empty. |
| AC-11 | Every drill-down deep link carries the required context parameters and returning preserves project, section, filters and (where practical) the expanded item — the user never re-selects a project. |
| AC-12 | No Control Center section reproduces a specialized route's full dataset, filters, or write controls. |
| AC-13 | Decision history displays superseded decisions, and no history entry is editable or removable in the UI. |
| AC-14 | With identity state `identity not verified`, no final decision can be submitted and a security notice explains the requirement. |
| AC-15 | A keyboard-only user can complete every legal review flow, including confirmation dialogs, with visible focus throughout. |
| AC-16 | Below 768px, no review action or final decision can be submitted, and an explicit unsupported-action message is shown instead of a hidden or silently disabled control. |
| AC-17 | `production_executed_true_count = 0` is visible on the Control Center and is read-only — no client control can alter or locally compute it. |
| AC-18 | Every not-yet-implemented capability (route, API, read model, identity) is labelled as planned/not available with its gating stage, and never presented as usable. |

## 5. Not authorized by this handoff

```text
Codex frontend implementation      Claude Code backend implementation
Route source modification          TASK_ROLES modification
API/event/audit contract change    ADR-66D-09 change
PR merge                           deployment
Step 67POC.0                       RA-2I0
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
