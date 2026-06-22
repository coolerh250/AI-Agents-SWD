"""Step 52.4 -- identity posture status constants (read-only aggregation).

No production state is ever represented: the only "good" status is
``modeled_fail_closed_not_enabled``. There is intentionally NO
``production_identity_ready`` / ``oidc_enabled`` status value.
"""

from __future__ import annotations

STATUS_MODELED = "modeled_fail_closed_not_enabled"
STATUS_FAILED = "failed"
STATUS_UNKNOWN = "unknown"

POSTURE_STATUSES = (STATUS_MODELED, STATUS_FAILED, STATUS_UNKNOWN)

# Safety invariants that must hold for the posture to be MODELED (fail-closed).
# Each maps a posture path to its required value. A mismatch -> status failed.
REQUIRED_FALSE = (
    "productionIdentityReady",
    "productionAuthEnabled",
    "testLocalProductionFallbackAllowed",
    "oidc.enabled",
    "oidc.productionEnabled",
    "oidc.discoveryFetched",
    "oidc.jwksFetched",
    "oidc.callbackEnabled",
    "oidc.tokenExchangeEnabled",
    "oidc.realProviderConfigured",
    "oidc.secretCommitted",
    "session.rawTokenPersisted",
    "roleMapping.platformAdminAutoGrant",
    "roleMapping.frontendRoleAuthority",
    "breakGlass.enabled",
    "breakGlass.routePresent",
    "authorization.humanAcceptanceIsDeployment",
    "authorization.platformAdminInfrastructureAuthority",
)

__all__ = [
    "STATUS_MODELED",
    "STATUS_FAILED",
    "STATUS_UNKNOWN",
    "POSTURE_STATUSES",
    "REQUIRED_FALSE",
]
