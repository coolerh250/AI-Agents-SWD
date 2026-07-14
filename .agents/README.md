# .agents — Stage Gate & Context Guard Skill Pack

> **Process documentation only. No backend/frontend runtime change. No workflow dispatch. No
> workflow resume. No external action. No production action.**

This directory is the repo-level enforcement mechanism for cross-partner collaboration on the AI
Agents Team Work project (Claude Code, Claude Design, Codex, and any future partner). It exists
because long context windows, unmerged Draft PRs, and local-only notes have repeatedly caused
partners to drift from the current shared state (see `docs/decisions/README.md` and the Step
66UI.2-FE.1 Delivery Package placement gap for concrete prior incidents).

## Principle

```text
Do not rely on partner memory. Make the repo the memory.
Make PR / verifier / checklist force every partner to re-read the latest shared context.
```

No partner — human or AI — should be expected to remember project rules across sessions. The rules
live here, in files every partner is required to read and every PR/verifier is required to check
for, before any task begins.

## Skills

| Skill | Purpose |
| --- | --- |
| [`skills/shared-context/SKILL.md`](skills/shared-context/SKILL.md) | What every partner must sync/review before starting any task, and what counts as source of truth. |
| [`skills/stage-gate/SKILL.md`](skills/stage-gate/SKILL.md) | The nine gates every stage passes through, their owners, evidence, and pass criteria. |
| [`skills/security-governance/SKILL.md`](skills/security-governance/SKILL.md) | Hard security/governance restrictions that apply to every stage regardless of role. |
| [`skills/design-collaboration/SKILL.md`](skills/design-collaboration/SKILL.md) | Claude Design's boundaries and handoff requirements. |
| [`skills/frontend-implementation/SKILL.md`](skills/frontend-implementation/SKILL.md) | Codex's boundaries and handoff requirements. |

## How this is enforced

- `docs/stages/stage-manifest-standard.yaml` — every stage declares its scope, allowed/forbidden
  paths, and required evidence in a manifest following this standard.
- `docs/stages/context-receipt-template.md` — every partner fills this out at the start of a stage
  to prove they synced and reviewed the current shared state.
- `docs/stages/stage-gate-report-template.md` — every stage reports its result against the nine
  gates defined in `skills/stage-gate/SKILL.md`.
- `.github/pull_request_template.md` — every PR must check off the Shared Context, Scope,
  Authorization, Safety, and Evidence sections before it can be considered complete.
- `scripts/verify_stage_gate_compliance.py` — a repo-level verifier confirming this skill pack
  itself stays intact and internally consistent.

See `docs/process/context-guard-protocol.md` and `docs/process/stage-gate-checkpoint-protocol.md`
for the full protocols this skill pack implements.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action. No Codex implementation authorized by this document. No
design PR merged. No deployment performed.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
