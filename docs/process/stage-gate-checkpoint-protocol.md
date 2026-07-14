# Stage Gate Checkpoint Protocol

> **Process documentation only. No backend/frontend runtime change. No production action.**

This protocol defines the standard flow every substantive stage on this project follows, and
restates who may decide what at each checkpoint. It formalizes the pattern already used
consistently across the Step 66UI.1 → 66UI.2 → 66UI.4 and Step 65/66 sub-stage sequences, as a
named, repo-level reference instead of an implicit convention.

## Standard flow

```text
1. Product direction        — Product Owner states intent/priority.
2. Design, if needed        — Claude Design produces a brief (docs/design/<stage>/).
3. Architecture / contract review — Claude Code reviews design/direction against runtime reality;
                                    publishes a contract/boundary if implementation may follow.
4. Implementation, if authorized  — Codex (or the relevant implementing partner) builds against the
                                    contract, only after explicit Product Owner authorization.
5. Implementation review    — Claude Code reviews the implementation for scope/safety/quality.
6. Product Owner validation — Product Owner gives the operator verdict on the actual result.
7. Explicit merge authorization — Product Owner authorizes a specific branch → target merge.
8. Merge                    — Claude Code executes exactly what was authorized.
9. Explicit deployment authorization — Product Owner authorizes a specific deployment to a specific
                                       environment.
10. Deployment               — Claude Code executes exactly what was authorized.
11. Post-deployment record   — Claude Code records the result; Product Owner may validate again.
```

Not every stage exercises every step — a design-review-only stage stops after step 3; a
documentation/governance stage (like Step 66GOV.1) stops even earlier, at the point where its own
technical review is complete. Skipping a step because it doesn't apply is correct; skipping a step
that does apply without recording why is a stop condition (`docs/process/stop-conditions.md`).

## Who decides what

```text
No partner can decide Product Owner acceptance.
Claude Code can report technical PASS / PASS_WITH_GAPS / FAIL.
Claude Design can report design ready / needs another round.
Codex can report implementation ready / build+tests pass.
Only Product Owner can give: product acceptance, merge authorization, and deployment authorization.
```

This is the same rule stated in `docs/process/role-responsibility-matrix.md` "Cross-cutting rule"
and `.agents/skills/stage-gate/SKILL.md` gates 6–8; it is repeated here because it is the single
most load-bearing rule in the whole protocol and the one most likely to be silently violated under
time pressure or a long context window.

## Relationship to the stage gate skill

Each numbered step above corresponds to one or more gates in
`.agents/skills/stage-gate/SKILL.md`:

```text
Step 1  -> (Product Owner decision, recorded under docs/decisions/ or progress.md)
Step 2-3 -> Architecture Direction Gate, Design Review Gate
Step 4-5 -> Implementation Efficiency Gate, Security/Governance Gate
Step 6  -> Product Owner Validation Gate
Step 7-8 -> Merge Gate
Step 9-10 -> Deployment Gate
Step 11 -> Post-deployment Review Gate
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
