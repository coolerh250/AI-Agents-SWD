# Forced Logout Model (Step 52.3)

Source: [forced-logout-model.yaml](../../infra/identity/forced-logout-model.yaml).

* **Session-level revoke:** supported today and **server-authoritative**
  (`store.revoke_session`). There is no frontend-only logout — the server marks
  the session `revoked`.
* **User-level forced logout:** modelled, not production-ready.
* **Role-change forced logout:** required; not implemented (role mapping is not
  configured yet).
* **Break-glass forced logout:** required; not implemented (break-glass is
  disabled).
* **Audit:** required; the reason is recorded, the raw token is never recorded.

A production admin identity is required before user-level / role-change forced
logout can be enabled. No Admin Console button and no production endpoint are
added in this step.
