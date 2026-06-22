# RBAC Current State (Step 52.1 / Stage 54A)

Backend-authoritative. Source:
[rbac-inventory.yaml](../../infra/identity/rbac-inventory.yaml);
`shared/sdk/operator_actions/rbac.py` + `action_catalog.py`.

| Role | Read | Add note | Request changes | Accept/Reject | Verification rerun | Deploy/Sync/GitHub/Prod |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| viewer | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| reviewer | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| operator | ✅ | ✅ | ✅ | ✅ | ✅ (allowlisted) | ❌ |
| platform_admin | ✅ | ✅ | ✅ | ✅ | ✅ (allowlisted) | ❌ |

`platform_admin` has the **same action set as operator** — the name grants **no**
Kubernetes / ArgoCD / GitHub / deploy / production authority. Critical actions
(deploy, GitHub PR/merge, production backup/restore, policy/budget edits, arbitrary
shell) exist only as **disabled** catalog entries (never executable). Frontend
hide/disable is UX only; the backend is authoritative.
