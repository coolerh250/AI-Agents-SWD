# Operator Acceptance Checklist (Step 64E)

> **Staging only — non-production only. No production action. No production secret. No external write.**

An operator checklist for accepting the **staging** demonstration. Tick each item after
following [operator-walkthrough-sop.md](operator-walkthrough-sop.md). This is a staging
acceptance aid, **not** a production readiness sign-off.

## Access
- [ ] Operator can establish the SSH local port-forward tunnel to `10.0.1.32`.
- [ ] Operator can open the Admin Console at `http://localhost:18000/admin`.

## Demo review
- [ ] Operator can see the demo project **SaaS User Management Module**.
- [ ] Operator can see the demo work item **WI-0001 "Create user CRUD API"**.
- [ ] Operator can see the agent executions (intake → requirement → development → qa → devops,
      all completed).
- [ ] Operator can see the audit evidence (`work_item_created`; audit log total grew).
- [ ] Operator can see the operational metrics (project=1, work items=1).

## Safety
- [ ] Operator can see the safety posture with `production_executed_true_count=0`.
- [ ] Operator confirms **no production action** occurred.
- [ ] Operator confirms **no live external integrations** (GitHub / Slack / LLM disabled/mocked).
- [ ] Operator confirms **no public exposure** (SSH tunnel only).

## Understanding
- [ ] Operator understands the known gaps (delivery package/release candidate gated;
      communication-gateway PyYAML gap; Vault dev/mock; HTTP-only tunnel).
- [ ] Operator understands the do-not-execute list.

## Result
- [ ] Staging demonstration **accepted** for review purposes (non-production). Claude Code does
      not decide production readiness.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
