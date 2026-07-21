# Recommended Next Five Executable Stages — Step 66ALIGN.1-CC

> **Analysis and documentation only. No implementation, merge, deployment, or runtime modification
> performed by this document. These are recommendations for the Product Owner / PM Coordinator to
> authorize — this document authorizes nothing itself.**

## Recommended sequence

```text
1. Step 66C.4-P — Reminder / Expiry Planning
   Claude Code produces the scheduler-mechanism decision (poller vs. Redis-Streams delayed
   message), confirms no new task-status value is needed, and hands Codex a frontend-implementation
   boundary for the real /clarification-reminders page, mirroring the FE.1x contract pattern.
   Rationale: closes the last M1 gap; low design risk; unblocks M2 entry.

2. Step 66C.4 — Reminder / Expiry Implementation + Review + Deploy + Validation
   Full Codex-implements / Claude-Code-reviews / preview-deploy / Product-Owner-validates / merge
   chain, exactly matching the FE.1C.1/FE.1D-S1 pattern already proven across this project.
   Rationale: completes M1.

3. Step 66D-ARCH — Delivery & Acceptance Data Model and API Contract (Claude Code, architecture-
   only, no implementation)
   Produces the frozen data model for delivery packages tied to real tasks, the 6-action
   acceptance-gate endpoint contract, and the RBAC scoping for who may Accept/Reject/Escalate --
   BEFORE any UI is designed against it. This directly answers this stage's own required question
   about whether the data model must be frozen before UI design (yes -- see alignment-
   statement.md).
   Rationale: prevents the highest-impact risk identified in risk-register.md (#2).

4. Step 66D-DESIGN — Delivery Inbox / Acceptance Gate / Approvals / DLQ-Retry UI Design (Claude
   Design, against the frozen 66D-ARCH contract)
   Rationale: the design-collaboration/SKILL.md chain (design -> Claude Code review -> Product
   Owner decision -> Codex authorization) should be followed exactly as it was for FE.1C/FE.1D,
   now applied to the actually-value-adding M2 milestone instead of further Admin Console polish.

5. Step 66D-S1 (or equivalent slice) — first Codex implementation slice of 66D, scoped no more
   broadly than the FE.1D-S1 precedent (one bounded, reviewable slice at a time), starting with
   whichever of {Delivery Inbox, Approvals P0, DLQ/Retry P0} the Product Owner judges highest value
   first.
   Rationale: keeps the established small-PR discipline; produces the first real M2 deliverable.
```

## Explicitly NOT recommended as next stages (see also alignment-statement.md)

```text
FE.1D-S2 (microcopy/field-label cleanup) -- safe to run in parallel if the Product Owner wants it
  for its own sake, but should not be sequenced AHEAD of 66C.4/66D-ARCH on any shared execution
  capacity, since it does not advance the critical path.
Any M6-labeled production-substrate work (real K8s/ArgoCD cluster, real secret store, real DR
  remediation) -- premature before M1-M5 are real; would also require its own, much larger,
  separate authorization and planning cycle that this alignment stage does not attempt to scope in
  detail (M6 is analyzed at the gate/requirement level in security-runtime-gates.md, not planned
  stage-by-stage here, since M1-M5 are not yet complete).
```

## Statement

Analysis and documentation only. No implementation, merge, deployment, or runtime modification
performed by this document. Recommendations only -- authorization remains with the Product Owner.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
