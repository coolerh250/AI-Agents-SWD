# Operator Acceptance Checklist (Step 64E, corrected in 64E-R)

> **Staging only — non-production only. No production action. No production secret. No external write.**

An operator checklist for accepting the **staging** demonstration. **Every item below is
operator-owned and cannot be completed by Claude Code.** Claude Code marks all items `pending`;
only the operator can tick a box / mark an item `confirmed` (or `failed`) after actually
performing the walkthrough. This is a staging acceptance aid, **not** a production readiness
sign-off.

For every item — **Verification owner:** Operator · **Evidence type:** operator confirmation ·
**Status:** pending / confirmed / failed.

## Access
- [ ] **1.** Operator can establish the SSH local port-forward tunnel to `10.0.1.32`.
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **2.** Operator can open the Admin Console at `http://localhost:18000/admin`.
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending

## Demo review
- [ ] **3.** Operator can see the demo project **SaaS User Management Module**.
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **4.** Operator can see the demo work item **WI-0001 "Create user CRUD API"**.
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **5.** Operator can see the agent executions (intake→requirement→development→qa→devops).
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **6.** Operator can see the audit evidence (`work_item_created`; audit log total grew).
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **7.** Operator can see the operational metrics (project=1, work items=1).
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending

## Safety
- [ ] **8.** Operator can see the safety posture with `production_executed_true_count=0`.
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **9.** Operator confirms **no production action** occurred.
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **10.** Operator confirms **no live external integrations** (GitHub / Slack / LLM disabled).
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **11.** Operator confirms **no public exposure** (SSH tunnel only).
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending

## Understanding
- [ ] **12.** Operator understands the known gaps (delivery/release gated; gateway PyYAML; Vault
      dev/mock; HTTP-only tunnel).
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending
- [ ] **13.** Operator understands the do-not-execute list.
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending

## Result
- [ ] **14.** Staging demonstration accepted for review purposes (non-production).
  - Verification owner: Operator · Evidence type: operator confirmation · Status: pending

**All items are `pending` until the operator completes
[operator-walkthrough-confirmation-form.md](operator-walkthrough-confirmation-form.md).** Claude
Code does not decide production readiness and cannot self-confirm these items.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
