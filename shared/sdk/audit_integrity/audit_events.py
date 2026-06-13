"""Stage 39 -- audit decision_type + notification event constants.

The vocabulary added by Step 37 (audit integrity remediation):

* Audit decision_types emitted to ``audit_logs``:
    ``audit_hmac_keyring_loaded``
    ``audit_hmac_keyring_invalid``
    ``audit_hmac_key_rotated``
    ``audit_signature_verified``
    ``audit_signature_key_missing``
    ``audit_direct_post_integrity_created``
    ``audit_direct_post_integrity_failed``
    ``audit_integrity_concurrency_verified``

* Notification event_types emitted to ``stream.notifications``:
    ``audit.keyring_loaded``
    ``audit.keyring_invalid``
    ``audit.direct_post_integrity_created``
    ``audit.direct_post_integrity_failed``
    ``audit.signature_key_missing``

These events stay inside the ``audit.*`` namespace which the
``DEFAULT_REAL_DELIVERY_DENYLIST`` blocks from real Discord delivery
(verified by ``test_real_discord_delivery_filter``). Tamper-evident
audit loop safety: the audit-service does NOT emit a fresh audit row
for every integrity write -- only the keyring-load event at startup
and the verify-chain summary event at verify time.

The ``artifact_refs`` shape is constrained:

* ``key_id`` (opaque), ``keyring_mode``, ``verification_mode``,
  ``signature_status``, ``direct_post_integrity_enabled``,
  ``production_executed=False`` -- never the key value.
"""

from __future__ import annotations

DECISION_AUDIT_HMAC_KEYRING_LOADED = "audit_hmac_keyring_loaded"
DECISION_AUDIT_HMAC_KEYRING_INVALID = "audit_hmac_keyring_invalid"
DECISION_AUDIT_HMAC_KEY_ROTATED = "audit_hmac_key_rotated"
DECISION_AUDIT_SIGNATURE_VERIFIED = "audit_signature_verified"
DECISION_AUDIT_SIGNATURE_KEY_MISSING = "audit_signature_key_missing"
DECISION_AUDIT_DIRECT_POST_INTEGRITY_CREATED = "audit_direct_post_integrity_created"
DECISION_AUDIT_DIRECT_POST_INTEGRITY_FAILED = "audit_direct_post_integrity_failed"
DECISION_AUDIT_INTEGRITY_CONCURRENCY_VERIFIED = "audit_integrity_concurrency_verified"

EVENT_AUDIT_KEYRING_LOADED = "audit.keyring_loaded"
EVENT_AUDIT_KEYRING_INVALID = "audit.keyring_invalid"
EVENT_AUDIT_DIRECT_POST_INTEGRITY_CREATED = "audit.direct_post_integrity_created"
EVENT_AUDIT_DIRECT_POST_INTEGRITY_FAILED = "audit.direct_post_integrity_failed"
EVENT_AUDIT_SIGNATURE_KEY_MISSING = "audit.signature_key_missing"

STAGE_39_DECISION_TYPES: tuple[str, ...] = (
    DECISION_AUDIT_HMAC_KEYRING_LOADED,
    DECISION_AUDIT_HMAC_KEYRING_INVALID,
    DECISION_AUDIT_HMAC_KEY_ROTATED,
    DECISION_AUDIT_SIGNATURE_VERIFIED,
    DECISION_AUDIT_SIGNATURE_KEY_MISSING,
    DECISION_AUDIT_DIRECT_POST_INTEGRITY_CREATED,
    DECISION_AUDIT_DIRECT_POST_INTEGRITY_FAILED,
    DECISION_AUDIT_INTEGRITY_CONCURRENCY_VERIFIED,
)

STAGE_39_NOTIFICATION_EVENTS: tuple[str, ...] = (
    EVENT_AUDIT_KEYRING_LOADED,
    EVENT_AUDIT_KEYRING_INVALID,
    EVENT_AUDIT_DIRECT_POST_INTEGRITY_CREATED,
    EVENT_AUDIT_DIRECT_POST_INTEGRITY_FAILED,
    EVENT_AUDIT_SIGNATURE_KEY_MISSING,
)

# ---------------------------------------------------------------------------
# Stage 42 -- audit chain forensics + controlled integrity repair.
# ---------------------------------------------------------------------------
DECISION_AUDIT_CHAIN_FORENSICS_STARTED = "audit_chain_forensics_started"
DECISION_AUDIT_CHAIN_FORENSICS_COMPLETED = "audit_chain_forensics_completed"
DECISION_AUDIT_CHAIN_FORENSICS_FAILED = "audit_chain_forensics_failed"
DECISION_AUDIT_CHAIN_REPAIR_DRY_RUN = "audit_chain_repair_dry_run"
DECISION_AUDIT_CHAIN_REPAIR_SKIPPED_UNSAFE = "audit_chain_repair_skipped_unsafe"
DECISION_AUDIT_CHAIN_REPAIR_STARTED = "audit_chain_repair_started"
DECISION_AUDIT_CHAIN_REPAIR_COMPLETED = "audit_chain_repair_completed"
DECISION_AUDIT_CHAIN_REPAIR_FAILED = "audit_chain_repair_failed"
DECISION_AUDIT_CHAIN_REPAIR_VERIFIED = "audit_chain_repair_verified"

EVENT_AUDIT_FORENSICS_COMPLETED = "audit.forensics_completed"
EVENT_AUDIT_FORENSICS_FAILED = "audit.forensics_failed"
EVENT_AUDIT_REPAIR_DRY_RUN = "audit.repair_dry_run"
EVENT_AUDIT_REPAIR_SKIPPED_UNSAFE = "audit.repair_skipped_unsafe"
EVENT_AUDIT_REPAIR_COMPLETED = "audit.repair_completed"
EVENT_AUDIT_REPAIR_FAILED = "audit.repair_failed"

STAGE_42_DECISION_TYPES: tuple[str, ...] = (
    DECISION_AUDIT_CHAIN_FORENSICS_STARTED,
    DECISION_AUDIT_CHAIN_FORENSICS_COMPLETED,
    DECISION_AUDIT_CHAIN_FORENSICS_FAILED,
    DECISION_AUDIT_CHAIN_REPAIR_DRY_RUN,
    DECISION_AUDIT_CHAIN_REPAIR_SKIPPED_UNSAFE,
    DECISION_AUDIT_CHAIN_REPAIR_STARTED,
    DECISION_AUDIT_CHAIN_REPAIR_COMPLETED,
    DECISION_AUDIT_CHAIN_REPAIR_FAILED,
    DECISION_AUDIT_CHAIN_REPAIR_VERIFIED,
)

STAGE_42_NOTIFICATION_EVENTS: tuple[str, ...] = (
    EVENT_AUDIT_FORENSICS_COMPLETED,
    EVENT_AUDIT_FORENSICS_FAILED,
    EVENT_AUDIT_REPAIR_DRY_RUN,
    EVENT_AUDIT_REPAIR_SKIPPED_UNSAFE,
    EVENT_AUDIT_REPAIR_COMPLETED,
    EVENT_AUDIT_REPAIR_FAILED,
)


def safe_keyring_artifact_refs(
    *,
    keyring_mode: str,
    active_key_id: str | None,
    known_key_ids: list[str] | None = None,
    valid: bool = True,
    invalid_reason: str | None = None,
    verification_mode: str | None = None,
    signature_status: str | None = None,
    direct_post_integrity_enabled: bool = True,
) -> dict:
    """Build an artifact_refs dict that is safe to attach to an audit row.

    The key bytes are never referenced. Only the opaque key_id +
    metadata fields described in the Stage 39 spec end up in
    ``artifact_refs``.
    """
    refs: dict = {
        "keyring_mode": keyring_mode,
        "key_id": active_key_id,
        "keyring_valid": valid,
        "direct_post_integrity_enabled": bool(direct_post_integrity_enabled),
        "production_executed": False,
    }
    if known_key_ids is not None:
        refs["known_key_ids"] = list(known_key_ids)
    if invalid_reason:
        refs["invalid_reason"] = invalid_reason
    if verification_mode:
        refs["verification_mode"] = verification_mode
    if signature_status:
        refs["signature_status"] = signature_status
    return refs


__all__ = [
    "DECISION_AUDIT_HMAC_KEYRING_LOADED",
    "DECISION_AUDIT_HMAC_KEYRING_INVALID",
    "DECISION_AUDIT_HMAC_KEY_ROTATED",
    "DECISION_AUDIT_SIGNATURE_VERIFIED",
    "DECISION_AUDIT_SIGNATURE_KEY_MISSING",
    "DECISION_AUDIT_DIRECT_POST_INTEGRITY_CREATED",
    "DECISION_AUDIT_DIRECT_POST_INTEGRITY_FAILED",
    "DECISION_AUDIT_INTEGRITY_CONCURRENCY_VERIFIED",
    "EVENT_AUDIT_KEYRING_LOADED",
    "EVENT_AUDIT_KEYRING_INVALID",
    "EVENT_AUDIT_DIRECT_POST_INTEGRITY_CREATED",
    "EVENT_AUDIT_DIRECT_POST_INTEGRITY_FAILED",
    "EVENT_AUDIT_SIGNATURE_KEY_MISSING",
    "STAGE_39_DECISION_TYPES",
    "STAGE_39_NOTIFICATION_EVENTS",
    "DECISION_AUDIT_CHAIN_FORENSICS_STARTED",
    "DECISION_AUDIT_CHAIN_FORENSICS_COMPLETED",
    "DECISION_AUDIT_CHAIN_FORENSICS_FAILED",
    "DECISION_AUDIT_CHAIN_REPAIR_DRY_RUN",
    "DECISION_AUDIT_CHAIN_REPAIR_SKIPPED_UNSAFE",
    "DECISION_AUDIT_CHAIN_REPAIR_STARTED",
    "DECISION_AUDIT_CHAIN_REPAIR_COMPLETED",
    "DECISION_AUDIT_CHAIN_REPAIR_FAILED",
    "DECISION_AUDIT_CHAIN_REPAIR_VERIFIED",
    "EVENT_AUDIT_FORENSICS_COMPLETED",
    "EVENT_AUDIT_FORENSICS_FAILED",
    "EVENT_AUDIT_REPAIR_DRY_RUN",
    "EVENT_AUDIT_REPAIR_SKIPPED_UNSAFE",
    "EVENT_AUDIT_REPAIR_COMPLETED",
    "EVENT_AUDIT_REPAIR_FAILED",
    "STAGE_42_DECISION_TYPES",
    "STAGE_42_NOTIFICATION_EVENTS",
    "safe_keyring_artifact_refs",
]
