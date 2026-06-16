# Operator RBAC Model (Stage 52)

Roles (backend-authoritative; frontend hide/disable is UX only):

| Role             | Capabilities                                                   |
| ---------------- | -------------------------------------------------------------- |
| `viewer`         | read-only; no actions                                          |
| `reviewer`       | add note, request changes (NOT accept/reject, NOT rerun)       |
| `operator`       | add note, request changes, accept, reject, allowlisted rerun   |
| `platform_admin` | same as operator — **no** deploy/GitHub/production by name     |

Forbidden permissions that are **never** created: `deployer`,
`production_admin`, `arbitrary_shell`, `github_write`.

RBAC is enforced in `shared/sdk/operator_actions/rbac.py` (`role_can`) against
the static action catalog. An action is permitted only when it is an
execution-enabled catalog entry AND the role is in its `allowed_roles`.
Disabled/unknown actions are always denied.

Identities + role grants live in `operator_identities` /
`operator_role_assignments`; sessions in `admin_console_sessions` (hash only).
No raw password / session token / secret is stored.
