# Identity Operations API (Step 52.4)

`apps/orchestrator/src/identity_posture_api.py` exposes 13 **GET-only**
read-only endpoints under `/operations/identity/*`:

`posture`, `authentication`, `session`, `csrf`, `rbac`, `operator-actions`,
`oidc`, `role-mapping`, `break-glass`, `audit-mapping`, `risks`, `readiness`,
`report`.

## Guarantees

* GET-only. No POST/PUT/PATCH/DELETE; no login / callback / authorize / token /
  logout / connect / role-mapping mutation / break-glass activation endpoint.
* No IdP connection, no discovery/JWKS fetch, no secret/key-file read, no
  subprocess, no user-provided path.
* Reads only the committed `identity-posture-summary.yaml`. Absent summary →
  `status: unknown` (never a fake PASS).
* Responses carry statuses / booleans / enums only — no token, secret, cookie /
  session signing secret, CSRF secret, raw email, real group ID, or
  chain-of-thought. The `break-glass` endpoint is a read-only view of the
  **disabled** state and grants nothing.

Verifier: `IDENTITY_OPERATIONS_VISIBILITY_VERIFY` (source guard + live GET check +
forbidden-endpoint check + posture/safety assertions).
