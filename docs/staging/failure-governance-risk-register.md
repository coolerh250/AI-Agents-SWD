# Failure / Governance Risk Register (Step 65H.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only. Risk classification governs which scenarios need explicit operator authorization.**

Risk classification for the Step 65H scenarios. **All HIGH-risk scenarios require explicit operator
authorization before execution.**

## Classification rule (from the spec)
A scenario is **HIGH** if it might: create an external write; change approval state; cause failure
injection; create DLQ/replay activity; touch runtime flags; or risk a production action.
**MEDIUM** = a controlled state change with no external effect. **LOW** = read-only.

## Register
| ID | Scenario | Risk | Why | Authorization |
|---|---|---|---|---|
| A1 | approval required | MEDIUM | creates a pending request (state), no external effect | 65H.2 template |
| A2 | approval granted | HIGH | changes approval state + resumes a workflow | explicit (65H.2) |
| A3 | approval denied | HIGH | changes approval state (terminal reject) | explicit (65H.2) |
| A4 | approval expired/timeout | HIGH | changes approval state; mechanism to confirm | explicit (65H.2) |
| A5 | operator action audit | LOW | read-only decision inspection | 65H.2 template |
| A6 | production action blocked | HIGH | risks a production action if the block fails | explicit (65H.2) |
| B1 | cancel before execution | HIGH | changes workflow state (terminate) | explicit (65H.3) |
| B2 | cancel during workflow | HIGH | changes workflow state | explicit (65H.3) |
| B3 | abort during workflow | HIGH | changes workflow state | explicit (65H.3) |
| B4 | ignore-after-abort | MEDIUM | expects a 409 refusal; no state change | 65H.3 template |
| B5 | late event ignored after abort | HIGH | delivers an event that could resume a workflow | explicit (65H.3) |
| B6 | Admin Console visibility | LOW | read-only | 65H.3 template |
| C1 | controlled agent failure | HIGH | failure injection | explicit (65H.4) |
| C2 | retry scheduler handling | HIGH | creates retry activity | explicit (65H.4) |
| C3 | DLQ creation | HIGH | creates DLQ activity | explicit (65H.4) |
| C4 | manual DLQ replay | HIGH | replay activity | explicit (65H.4) |
| C5 | terminal failure state | HIGH | failure/terminal activity | explicit (65H.4) |
| C6 | retry count limit | MEDIUM | verifies `max_retries=3` bound | 65H.4 template |
| C7 | failure evidence visibility | LOW | read-only | 65H.4 template |
| D1 | production-effect task blocked | HIGH | risks production dispatch | explicit (65H.2/H.4) |
| D2 | production deployment blocked | HIGH | risks a deploy | explicit |
| D3 | prod-executed stays 0 | LOW | read-only safety check | any |
| D4 | external write blocked | HIGH | risks an external write | explicit |
| D5 | kill switch effectiveness | LOW | read-only flag check | any |

## Summary
- **HIGH:** A2, A3, A4, A6, B1, B2, B3, B5, C1–C5, D1, D2, D4 → each requires explicit operator
  authorization in its sub-stage template.
- **MEDIUM:** A1, B4, C6 → controlled, non-external state changes; still per-sub-stage authorized.
- **LOW:** A5, B6, C7, D3, D5 → read-only, no authorization gate beyond the sub-stage itself.

## Execution outcome (65H.2–65H.4) + review (65H.5)
- All HIGH/MEDIUM scenarios were exercised under their per-sub-stage operator authorization and
  passed, except the tracked gaps (approval expiry/timeout; raw late-stream-event injection), which
  were not executed for safety reasons (no safe route / unsafe injection forbidden).
- **65H.5** consolidated the results: **65H = COMPLETED_WITH_GAPS**, **no BLOCKING gap**; remaining
  items are acceptable-for-staging or operator-UX / product-backlog (see
  [failure-governance-gap-classification.md](failure-governance-gap-classification.md)). The
  operator-flagged **DLQ / Retry Admin Console page** gap is registered in
  [failure-governance-operator-ux-gap-register.md](failure-governance-operator-ux-gap-register.md).

## This stage's posture
Planning + review only. No scenario executed in the plan (65H.1) or the review (65H.5); no external
write; no LLM call; no Discord send; no production action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
