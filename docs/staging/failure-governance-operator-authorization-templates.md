# Failure / Governance Operator Authorization Templates (Step 65H.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — the operator fills these in to authorize each execution sub-stage.**

No 65H execution sub-stage runs until the operator returns the matching template. Claude Code does
not self-authorize any scenario.

## 65H.2 — Approval & Governance
```
Step 65H.2 — Approval & Governance Path Validation — operator authorization
- approval required path ........... [ ] YES  [ ] NO
- approval granted path ............ [ ] YES  [ ] NO
- approval denied path ............. [ ] YES  [ ] NO
- approval expired path ............ [ ] YES  [ ] NO
- production block path ............ [ ] YES  [ ] NO
- external actions allowed ......... [ ] YES  [ ] NO   (default NO)
- max workflow count ............... [ ____ ]
- operator UI validation ........... [ ] YES  [ ] NO
```

## 65H.3 — Cancel / Abort / Ignore-after-abort
```
Step 65H.3 — Cancel / Abort / Ignore-after-abort Validation — operator authorization
- cancel before execution .......... [ ] YES  [ ] NO
- cancel during workflow ........... [ ] YES  [ ] NO
- abort during workflow ............ [ ] YES  [ ] NO
- ignore-after-abort validation .... [ ] YES  [ ] NO
- max workflow count ............... [ ____ ]
- external actions allowed ......... [ ] YES  [ ] NO   (default NO)
- operator UI validation ........... [ ] YES  [ ] NO
```

## 65H.4 — Retry / DLQ / Manual Replay
```
Step 65H.4 — Retry / DLQ / Manual Replay Validation — operator authorization
- controlled agent failure ......... [ ] YES  [ ] NO
- retry scheduler validation ....... [ ] YES  [ ] NO
- DLQ creation ..................... [ ] YES  [ ] NO
- manual replay .................... [ ] YES  [ ] NO
- terminal failure ................. [ ] YES  [ ] NO
- max retry count .................. [ ____ ]   (platform default 3)
- max replay count ................. [ ____ ]
- external actions allowed ......... [ ] YES  [ ] NO   (default NO)
- operator UI validation ........... [ ] YES  [ ] NO
```

## Standing constraints (all templates)
- No production action / deploy / sync / secret / data. No merge/release/tag. No image push. No
  public exposure. No volume deletion. No full-stack restart. No retry storm. No DLQ replay beyond
  the authorized count. No approval-state change outside the authorized case. All external rails
  (GitHub/Discord/LLM) go through their controlled paths only, and only if explicitly authorized
  above (default NO). `production_executed_true_count` must remain 0.

## After authorization
Each sub-stage executes strictly within the authorized scenarios and counts, captures formal-page
evidence, resets to safe, and requests operator UI validation. **Claude Code must not decide staging
functional acceptance** — that is the operator's Step 65I verdict.

## This stage's posture
Planning only. No scenario executed; no external write; no LLM call; no Discord send; no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
