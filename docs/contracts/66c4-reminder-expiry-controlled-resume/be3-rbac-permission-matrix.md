# Step 66C.4-BE3-P — RBAC and Permission Matrix

> **Planning/contract document only. No RBAC code implemented. Reuses the six canonical
> `shared/sdk/tasks/rbac.py` `TASK_ROLES` verbatim; it does NOT create a second parallel RBAC.**

## A. Role model (abstract lens -> canonical roles)

The prompt's five abstract roles are a readability lens over the six real `TASK_ROLES`
(`requester`, `pm_engineering_lead`, `reviewer_approver`, `platform_admin`, `agent_operator`,
`security_compliance_reviewer`). No new role name is introduced.

```text
Viewer                 -> any TASK_ROLE with view access (requester scoped to own task/project).
Operator               -> {pm_engineering_lead, platform_admin, agent_operator}
                          (the existing can_request_resume set).
Approver               -> {reviewer_approver}  (human authorizer for replay; distinct from Operator).
Platform Administrator -> {platform_admin}     (operational recovery + explicit policy override).
Service Identity       -> a non-human service principal (orchestrator / relay executor). NOT a
                          TASK_ROLE; a scoped machine credential that may EXECUTE authorized
                          commands only and can never request or authorize.
Audit visibility       -> {security_compliance_reviewer} (read-only evidence; no action rights).
```

## B. Actions

```text
view clarification state, view resume eligibility, request resume, authorize resume, reject resume,
cancel pending resume request, execute resume, view dead outbox event, request replay,
authorize replay, execute replay, view authorization evidence, override policy
```

## C. Permission matrix

Legend: Y = allowed; N = denied; own = allowed but scoped to own task/project; policy = performed by
the automated policy/safety evaluation, not a human; svc = performed by the Service Identity under a
prior human authorization; prod = additionally requires the separate production-effect approval.

```text
Action                      | requester | pm_eng_lead | agent_operator | platform_admin | reviewer_approver | sec_compliance | Service Identity
--------------------------- | --------- | ----------- | -------------- | -------------- | ----------------- | -------------- | ----------------
view clarification state    | own       | Y           | Y              | Y              | Y                 | Y              | N
view resume eligibility     | N         | Y           | Y              | Y              | N                 | Y (audit)      | N
request resume              | N         | Y           | Y              | Y              | N                 | N              | N
authorize resume            | policy    | policy      | policy         | policy         | policy            | N              | N
reject resume               | N         | Y           | Y              | Y              | N                 | N              | N
cancel pending resume req   | N         | Y (own req) | Y (own req)    | Y              | N                 | N              | N
execute resume              | N         | N           | N              | N              | N                 | N              | svc
view dead outbox event      | N         | Y           | Y              | Y              | N                 | Y (audit)      | N
request replay              | N         | Y           | Y              | Y              | N                 | N              | N
authorize replay            | N         | N           | N              | Y*             | Y                 | N              | N
execute replay              | N         | N           | N              | N              | N                 | N              | svc
view authorization evidence | own       | Y           | Y              | Y              | Y                 | Y              | N
override policy             | N         | N           | N              | Y (audited)    | N                 | N              | N
```

`*` platform_admin may authorize replay ONLY when it is not the same principal that requested it
(two-person control, D2). production-effect resume/replay additionally requires the separate
production approval (prod), which no role in this matrix may bypass.

## D. Binding separation rules (PO decisions)

```text
D1. Self-request/self-authorize:
    - Normal non-production RESUME: the authorizer is the automated policy/safety check (no human
      "authorizer"); an Operator requesting their own resume is permitted because the policy check
      -- not the requester -- is the gate.
    - Dead-event REPLAY: two-person control. The principal that requested a replay MUST NOT be the
      principal that authorizes it (requester_principal != approver_principal), enforced at the
      authorize step.
D2. Two-person replay control: REQUIRED. Approver in {reviewer_approver, platform_admin(!=requester)}.
D3. Platform Administrator override: allowed ONLY through the explicit, always-audited
    `override policy` permission; it is never silent and never applies to a production-effect task.
D4. Service Identity: may EXECUTE resume/replay commands that carry a valid, unexpired, unconsumed
    durable authorization; it can never create a request and never authorize one.
D5. Production-effect separation: a production-effect task requires Operator request + the existing
    production approval gate + policy authorization; the resume/replay authorization here does NOT
    replace or weaken the production approval gate.
```

## E. Proposed capability functions (naming/shape follows `shared/sdk/tasks/rbac.py`; NOT implemented here)

```python
_REQUEST_RESUME_ROLES  = {"pm_engineering_lead", "platform_admin", "agent_operator"}   # existing
_REQUEST_REPLAY_ROLES  = {"pm_engineering_lead", "platform_admin", "agent_operator"}
_AUTHORIZE_REPLAY_ROLES = {"reviewer_approver", "platform_admin"}   # subject to requester != approver
_OVERRIDE_POLICY_ROLES = {"platform_admin"}                          # always audited; never production
# execute_* is a Service-Identity-only path gated on a durable authorization, not a TASK_ROLE.
```

Reuse note: `can_request_resume` / `can_view_resume_eligibility` already exist in
`rbac-and-safety-contract.md`; BE3 reuses them and adds only the replay/override checks above. No
general-purpose permission engine is introduced.

## Statement

Planning/contract document only. No RBAC code implemented. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
