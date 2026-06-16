# Operator Action Policy Model (Stage 52)

Each governed action flows through (fail-closed at every step):

1. Authenticate identity (signed session cookie).
2. Verify session (active, not expired/revoked) + identity active.
3. Verify CSRF (`X-CSRF-Token`, HMAC-bound to the session).
4. Verify RBAC (role permitted for the action type).
5. Validate target + reason (non-empty).
6. Validate action policy (catalog: execution-enabled, risk, confirmation).
7. Create `operator_action_request`.
8. Require one-time confirmation nonce when configured.
9. Execute the concrete (reversible) effect.
10. Store `operator_action_execution`.
11. Write audit event (Step 37 integrity path).
12. Emit a default-denied notification.
13. Return the action result (`production_executed=false`, etc.).

## Policy-engine integration

The action request calls the platform policy-engine
(`shared/sdk/operator_actions/policy_gate.py`). Input: identity, role,
action_type, target, environment, risk_level, `production_executed=false`. If
the policy-engine is unavailable, the gate **fails closed** (action blocked).

## Approval / confirmation

Delivery package accept / reject / request-changes and verification rerun are
explicit human operator actions — they require a **second confirmation** (a
short-lived, one-time, identity-bound nonce; 5-minute expiry) rather than a
separate approval-engine human approval. `full_regression` rerun additionally
requires a higher confirmation acknowledgement (`high_risk_ack`). Future
high-risk actions would require the approval-engine; they stay disabled this
stage.

## Idempotency

Every action requires an `Idempotency-Key`. A repeated request returns the
existing action result rather than re-executing (enforced by a unique key in
`operator_action_requests`).
