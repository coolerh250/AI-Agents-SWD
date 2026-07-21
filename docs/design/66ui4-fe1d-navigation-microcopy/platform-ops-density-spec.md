# Platform Ops Density Spec — Step 66UI.4-FE.1D

> Owner: Claude Design. Minimal density polish for the 20-item Platform Ops nav group (`Nav.tsx`).
> Addresses the FE.1A-recorded non-blocking "Platform Ops compact density" gap. **Label / subtitle /
> marker / ordering / optional visual sub-grouping only — no route change, no cross-group move, no
> IA restructure.**

## Baseline

Platform Ops = 20 items, `collapsible: true`, `defaultExpanded: false` (collapsed by default — good).
When expanded it is a long, flat, equally-weighted list of mostly read-only DevOps/governance pages,
several with long engineering labels.

## 1. Keep it collapsed + compact density

- Keep `defaultExpanded: false`.
- Render expanded items in the **compact** density on the quiet surface (per Phase 1 visual-language
  `--surface-quiet`) so the group reads clearly as "advanced / platform maintenance," subordinate to
  the core product groups. (Visual-token application, no new tokens.)

## 2. Shorten long labels (display only)

| Current label | Shorter label |
| --- | --- |
| "Sandbox GitHub Draft PR" | "Sandbox GitHub" |
| "Controlled Rollout Review" | "Rollout Review" |
| "Production Readiness Gate" | "Production Readiness" |
| "Backup / Restore / DR" | "Backup & DR" |
| "Security / Supply Chain" | "Security" |
| "Workflows / Task Graph" | "Task Graph" |
| "Projects / Work Items" | "Work Items" (subtitle "Multi-project delivery") |

Route and destination unchanged.

## 3. Read-only / diagnostic / evidence markers (small tag or subtitle)

Most Platform Ops pages are read-only posture views. Add a small marker so users know they are
looking, not operating:

| Item(s) | Marker |
| --- | --- |
| Runtime Baseline, Identity Posture, Secret Posture, Security, Release Governance, Backup & DR, Production Readiness, Rollout Review | **Read-only** |
| Task Graph, Design Review, Workspace Execution, Mini Delivery Pilot, Delivery Package, QA / Code | **Evidence** |
| Operational Metrics, Regression, Cost / LLM | **Read-only** |
| Demo Evidence (not in nav) | **Diagnostic** (unchanged; direct route only) |

Markers are text tags (not color-only).

## 4. Optional non-structural visual sub-grouping (within the same group)

To lower cognitive load **without** changing the IA or routes, optionally insert lightweight
non-interactive sub-headers inside the Platform Ops group (visual dividers/labels only — still one
nav group, no new routes):

```text
Platform Ops
  — Delivery & QA:      Work Items · Task Graph · Design Review · Workspace Execution ·
                        Mini Delivery Pilot · Delivery Package · QA / Code
  — Security & Identity:Identity Posture · Secret Posture · Security
  — Release & Runtime:  Release Governance · Rollout Review · Production Readiness ·
                        Runtime Baseline · Backup & DR · Sandbox GitHub
  — Metrics:            Operational Metrics · Regression · Cost / LLM
```

This is a **presentation** grouping (sub-labels + ordering), not a routing or nav-config
restructure. If Claude Code prefers to avoid even sub-headers in FE.1D, fall back to #1–#3 only
(labels + markers + compact density).

## 5. Minimal, not a reorg

FE.1D does the **least** that reduces density: collapsed + compact (already collapsed), shorter
labels, read-only/evidence markers, and — optionally — visual sub-headers. A real reorganization of
Platform Ops into separate nav groups or new routes is **out of scope** and would be a future IA
stage.

## Out of scope (FE.1D)

- No new routes, no route-target changes, no moving items out of Platform Ops.
- No page-content changes to any Platform Ops page.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
