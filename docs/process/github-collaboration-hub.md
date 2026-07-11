# GitHub Collaboration Hub

> **Process documentation only. No backend/frontend runtime change. No workflow dispatch. No
> workflow resume. No external action. No production action.**

GitHub (`coolerh250/AI-Agents-SWD`) is the **single source of truth** for this project's code,
design documents, API contracts, frontend handoffs, validation records, known gaps, progress, and
decisions. There is no separate design tool, ticket tracker, or wiki of record — if it isn't in this
repository, it isn't part of the project record.

## Data exchange paths

| Producer | Path | Content |
| --- | --- | --- |
| Claude Design | `docs/design/<stage>/*` | design brief, wireframe notes, interaction flow, component spec |
| Claude Code | `docs/contracts/<stage>/*` | API contract, data contract, RBAC error contract, safety contract |
| Codex | `docs/frontend/<stage>/*` | implementation plan, test evidence, handoff report |
| Claude Code (integration) | `docs/test/<stage>/*` | implementation report, evidence, security/safety records, deployment record, known gaps, operator validation request |
| Operator validation | `docs/test/<stage>-operator-validation-record.md` | the operator's verbatim verdict and per-item checklist |
| Long-term decisions | `docs/decisions/*` | ADRs — architectural/process decisions that outlive a single stage |
| Progress | `source/progress.md` | the canonical, append-only stage-by-stage log — one section per stage, status/marker/gate |

## How the paths connect

`docs/design/<stage>/` → `docs/contracts/<stage>/` → `docs/frontend/<stage>/` →
`docs/test/<stage>/` → `docs/test/<stage>-operator-validation-record.md` → `source/progress.md`.
Each stage folder is named after its Step 66 sub-stage (e.g. `66c3-workroom-audit-visibility`,
matching the existing `docs/test/step66c3-*` naming already in use), so a reviewer can find every
artifact for a given stage by searching for that one name across `docs/`.

`docs/decisions/*` is not stage-scoped — it holds decisions that apply across stages (e.g. "we use a
test-only header role simulation instead of a real session until 66S", already an established
project-wide decision).

## Repository is public

`coolerh250/AI-Agents-SWD` is a **public** GitHub repository. See
`docs/process/operator-validation-standard.md` and the masking rule restated in every doc this stage
creates — no internal infrastructure identifier, credential, or secret may appear in anything
committed here.

## Statement

Documentation only. No backend/frontend runtime change occurred. No workflow dispatch occurred. No
workflow resume occurred. No external action occurred. No production action occurred.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets in docs, examples, screenshots, or validation evidence — use neutral labels such as "test
host", "internal test runtime", "admin console local tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
