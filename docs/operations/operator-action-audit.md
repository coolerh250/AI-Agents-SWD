# Operator Action Audit (Stage 52)

Every operator action emits an audit event via the Step 37 integrity path
(`stream.audit` → audit-worker). Decision types
(`shared/sdk/operator_actions/audit_events.py`):

`operator_session_created`, `operator_session_revoked`,
`operator_action_requested`, `operator_action_policy_blocked`,
`operator_action_confirmed`, `operator_action_completed`,
`operator_action_failed`, `operator_review_note_added`,
`delivery_package_operator_accepted`, `delivery_package_operator_rejected`,
`delivery_package_changes_requested`, `verification_rerun_started`,
`verification_rerun_completed`, `verification_rerun_failed`.

Audit `artifact_refs` carry only opaque ids / labels / statuses
(`safe_operator_action_refs`) — never a raw token, secret, full reason dump, or
chain-of-thought. `production_executed`, `github_write_performed`, `pr_created`,
`deployment_performed`, `external_delivery_performed` are always false.

## Notifications

`operator_action.*`, `operator_review.*`, `verification_rerun.*` are
**default-denied** for real external delivery (added to
`shared/sdk/notifications/real_delivery_policy.py`'s denylist; all prior
namespaces remain). Events publish to `stream.operator_actions` (sandbox only).

## Action trail

`operator_action_requests` → `operator_action_executions` /
`operator_action_confirmations` / `operator_action_audit_links`. Read-only via
`GET /operations/admin-console/operator-actions` and
`GET /operations/delivery-packages/{id}/operator-review/history`.

## Audit integrity

Operator actions never modify `audit_integrity_records` or `audit_logs`
directly, never change canonicalization, and never lower verifier strictness.
`verify_tamper_evident_audit.sh` and `detect_audit_tamper_residue.sh` remain
authoritative.
