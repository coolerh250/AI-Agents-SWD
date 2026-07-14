# Stage Gate Report Template

> **Process documentation only. No backend/frontend runtime change. No production action.**

Fill this out at the end of any stage, reporting the result of each gate defined in
`.agents/skills/stage-gate/SKILL.md` that applies to this stage (mark non-applicable gates as
"N/A — <reason>" rather than omitting them).

```text
Shared Context Sync Gate:
Architecture Direction Gate:
Design Review Gate:
Implementation Efficiency Gate:
Security / Governance Gate:
Product Owner Validation Gate:
Merge Gate:
Deployment Gate:
Post-deployment Review Gate:
Final gate result:
Open gaps:
Accepted gaps:
Blocking gaps:
Next authorized step:
```

## Notes

- Each gate line should state `PASS`, `PASS_WITH_GAPS`, `FAIL`, or `N/A — <reason>`, plus one short
  clause of supporting evidence (e.g. "PASS — production_executed_true_count 0 before/after").
- `Final gate result` is the overall stage verdict; it should not read `PASS` if any exercised gate
  reads `FAIL`.
- `Open gaps` / `Accepted gaps` / `Blocking gaps` should be mutually exclusive lists — an accepted
  gap has explicit Product Owner sign-off; a blocking gap prevents `Final gate result` from being
  `PASS`; an open gap is neither yet.
- Only the Product Owner may move a gap from `Open` to `Accepted`
  (`.agents/skills/stage-gate/SKILL.md` §6).

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
