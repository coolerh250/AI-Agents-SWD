# AI Agents Team Work — User Role Model (Step 66A.1)

> **Planning / discovery only. No UI implementation. No production action. Recommended defaults are non-final and require operator review.**

Operator decision **D1: primary users = multi-role.** This model defines the roles and **recommended
default** permissions. Exact permissions are **not finalized** — they require operator review (see
decision register D1).

## 1. Roles

1. **System owner** — ultimate authority; manages the platform and all roles.
2. **Platform / IT admin** — runs the runtime, integrations, secrets, environments.
3. **Project manager** — assigns tasks, tracks delivery, accepts/rejects work.
4. **Engineering lead** — technical review, approvals, request-changes, re-run QA.
5. **Requester** — submits task requests; limited visibility to own tasks.
6. **Reviewer / approver** — approves governed actions and deliveries.
7. **Agent operator** — operates agent runs; retry/replay; clarification handling.
8. **Security / compliance reviewer** — audit, policy, security-review sign-off.

## 2. Recommended default permission matrix (NON-FINAL — operator review required)

| Capability | Owner | Platform admin | PM | Eng lead | Requester | Reviewer | Agent operator | Sec/compliance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Create task | ✔ | ✔ | ✔ | ✔ | ✔ | ✖ | ✔ | ✖ |
| Approve governed action | ✔ | ✔ | ✔ | ✔ | ✖ | ✔ | ✖ | ✔ |
| Accept delivery | ✔ | ✖ | ✔ | ✔ | own only | ✔ | ✖ | ✖ |
| Request changes | ✔ | ✖ | ✔ | ✔ | own only | ✔ | ✖ | ✖ |
| Trigger retry / manual replay | ✔ | ✔ | ✖ | ✖ | ✖ | ✖ | ✔ | ✖ |
| View audit | ✔ | ✔ | ✔ | ✔ | own only | ✔ | ✔ | ✔ |
| Manage integrations / secrets | ✔ | ✔ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ |
| Manage team templates | ✔ | ✔ | ✔ | ✖ | ✖ | ✖ | ✖ | ✖ |
| Answer clarification | ✔ | ✔ | ✔ | ✔ | own only | ✔ | ✔ | ✖ |

Legend: ✔ allowed (default) · ✖ not allowed (default) · "own only" = scoped to the user's own tasks.

## 3. Design notes

- Map channel identity (Slack/Discord/Telegram/API caller) → platform role before honoring any
  privileged action (see intake model). Unmapped identity = requester-level or rejected.
- Retry/replay and integration/secret management are **restricted** by default (platform admin / agent
  operator / owner) to protect governance and Step 65's `production_executed_true_count=0` invariant.
- These are **recommended defaults only** — final RBAC is decision item **D1**, pending operator
  answer before 66A.3.

## 4. Statement

No permissions were implemented; this is a discovery model. Recommendations are non-final. No
production action occurred.

## Recorded decision (66A.2)

**D1 = B — Conservative RBAC.** General users create + track tasks; PM / Engineering Lead / Reviewer
review + accept delivery; Platform Admin / Agent Operator manage retry, replay, integrations, and
higher-risk operations. The recommended default matrix in §2 stands as the **66A.3 starting point**
(the exact per-capability matrix is still to be signed off by the operator at 66A.3).

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
