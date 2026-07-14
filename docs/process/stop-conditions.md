# Stop Conditions

> **Process documentation only. No backend/frontend runtime change. No production action.**

Any partner encountering one of the conditions below must **stop and report it** rather than
proceeding, guessing, or resolving it silently in either direction. Reporting a stop condition is
not a failure — proceeding past one without reporting it is.

## Conditions

```text
1. Prompt conflicts with shared docs.
   The task prompt assumes or states something that source/progress.md, main, or docs/decisions/
   directly contradicts.

2. main conflicts with Draft PR decision.
   A Draft PR records a decision that the actual merged/deployed state on main no longer matches
   (e.g. a design PR's placement decision that a later merged implementation changed).

3. Missing Product Owner authorization for merge/deploy/production/external action.
   Any of these four actions is about to happen, or is requested, without an explicit, scoped
   Product Owner authorization naming that specific action.

4. Codex task requires backend change.
   A frontend implementation task, as scoped, cannot be completed without a backend/API/database
   change that hasn't been authorized via a Claude Code contract.

5. Claude Design request implies API or workflow change.
   A design brief or direction requires new backend capability, a new endpoint, or a workflow
   dispatch/resume behavior that doesn't exist and hasn't been contracted.

6. Secret / internal identifier found.
   A secret shape, token, internal IP, SSH alias, private hostname, or credential is found in any
   file about to be read, written, or committed.

7. Verifier fails unexpectedly.
   A verifier that previously passed now fails without an intentional, explained change (as
   opposed to an expected lifecycle flip, e.g. a pre-merge-gate verifier correctly failing after
   its gate condition is fulfilled by an authorized merge — see
   docs/frontend/66ui2-navigation-ia/merge-record.md for that distinction being made explicitly).

8. Security / governance scope unclear.
   It is not clear whether a proposed action falls inside or outside the hard restrictions in
   .agents/skills/security-governance/SKILL.md.
```

## What "stop and report" means in practice

- Do not proceed with the ambiguous or unauthorized action.
- State the specific condition triggered, the evidence for it, and the two (or more) ways it could
  be resolved.
- Wait for the Product Owner (or, for a purely technical ambiguity, Claude Code) to resolve it
  before continuing that part of the task. Other, unaffected parts of the stage may continue if
  they are genuinely independent of the blocked item.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
