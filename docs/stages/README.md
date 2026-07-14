# Stage Manifests, Receipts, and Gate Reports

> **Process documentation only. No backend/frontend runtime change. No production action.**

This directory holds the repo-level standards a stage uses to declare its scope and prove its
context was synced, per the Stage Gate & Context Guard Skill Pack
(`.agents/README.md`, Step 66GOV.1).

## Files

| File | Purpose |
| --- | --- |
| `stage-manifest-standard.yaml` | The schema every stage's manifest should follow (fields, defaults, required-evidence list, stop conditions). |
| `context-receipt-template.md` | Filled out by a partner at the start of a stage to prove they synced/reviewed current shared context. |
| `stage-gate-report-template.md` | Filled out at the end of a stage to record the result of each of the nine gates in `.agents/skills/stage-gate/SKILL.md`. |
| `examples/design-stage-manifest.example.yaml` | Example manifest for a design-only review stage. |
| `examples/frontend-stage-manifest.example.yaml` | Example manifest for an authorized frontend-implementation stage. |
| `examples/review-stage-manifest.example.yaml` | Example manifest for a review/governance-only stage (like this one). |

## Usage

A stage manifest is not mandatory infrastructure (there is no automated gate blocking a stage
without one yet — see `docs/process/context-guard-protocol.md` "Future enforcement"), but any new
non-trivial stage should produce one under `docs/stages/<stage-slug>-manifest.yaml` following the
standard, so the stage's own scope/allowed-paths/required-evidence declaration lives in a
machine-checkable file rather than only in prose.

## Statement

Documentation only. No backend/frontend runtime change. No workflow dispatch. No workflow resume.
No external action. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
