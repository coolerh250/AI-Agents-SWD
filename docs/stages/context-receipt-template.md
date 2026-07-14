# Context Receipt Template

> **Process documentation only. No backend/frontend runtime change. No production action.**

Fill this out at the start of any stage, before doing any substantive work, per
`.agents/skills/shared-context/SKILL.md` and `docs/process/context-guard-protocol.md`. Paste the
completed receipt into the stage's own doc or completion report.

```text
Stage:
Partner:
Latest main commit reviewed:
Skill files reviewed:
source/progress.md reviewed:
Stage manifest reviewed:
Relevant design docs reviewed:
Relevant contract docs reviewed:
Relevant frontend docs reviewed:
Relevant handoffs reviewed:
Relevant PRs / branches reviewed:
New information found:
Conflicts found:
Decision: proceed / stop for clarification
How new information affected execution:
```

## Optional: document checksum / commit reference section

For stages that need to prove a specific document's content was reviewed at a specific point in
time (e.g. reviewing an unmerged Draft PR whose branch may later change), record the exact commit
hash of the branch/PR reviewed:

```text
Document: <path>
Commit reviewed: <hash>
Branch / PR: <name / number>
```

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
