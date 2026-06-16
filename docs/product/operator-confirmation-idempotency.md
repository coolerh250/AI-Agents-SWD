# Operator Confirmation & Idempotency (Stage 52)

## Confirmation nonce

- Generated server-side (`secrets.token_urlsafe`), returned to the client once.
- Only the SHA-256 hash is persisted (`operator_action_confirmations.nonce_hash`)
  — the raw nonce is never stored.
- One-time use: marked `used` on execute; reuse is rejected.
- Expiry: 5 minutes (`expires_at`); expired nonces are rejected.
- Identity-bound: must be confirmed by the same identity that requested it.

Validation: `shared/sdk/operator_actions/confirmation.py:confirmation_valid()`
returns `(ok, reason)` where reason ∈ {confirmation_already_used,
confirmation_identity_mismatch, confirmation_expired, confirmation_invalid, ok}.

Required for: accept, reject, request_changes, verification.rerun
(`full_regression` requires a higher-confirmation acknowledgement). Adding a
review note is low-risk and needs no confirmation.

## Idempotency

- Every mutating call carries an `Idempotency-Key` header
  (`shared/sdk/operator_actions/idempotency.py` validates shape).
- The key is unique in `operator_action_requests`; a duplicate request returns
  the existing action (`idempotent_replay: true`) and does not re-execute.
- This prevents double-accept / double-reject / duplicate verification reruns.
