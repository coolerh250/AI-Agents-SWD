"""Step 52.2 -- production identity / OIDC abstraction (disabled, no network).

Pure model + loader + policy layer for a FUTURE production OIDC provider. It
performs NO discovery fetch, NO JWKS fetch, NO authorization-code exchange, NO
token validation, and creates NO session. Production OIDC stays disabled and
fail-closed; test-local signed sessions remain the only active (non-production)
auth path (owned by ``shared.sdk.operator_actions.auth``, unmodified here).
"""

from __future__ import annotations

from shared.sdk.identity.oidc_config import (
    OidcValidationResult,
    load_oidc_config,
    validate_oidc_inputs,
)
from shared.sdk.identity.oidc_models import (
    ALLOWED_ROLES,
    OidcClaimContract,
    OidcConfigStatus,
    OidcProviderConfig,
    SecretRef,
)
from shared.sdk.identity.oidc_policy import (
    REQUIRED_POLICY_KEYS,
    load_oidc_policies,
    policy_keys,
)
from shared.sdk.identity.oidc_provider import (
    OidcDisabledError,
    OidcProvider,
    OidcProviderError,
)
from shared.sdk.identity.oidc_redaction import contains_secret_like, find_secret_like
from shared.sdk.identity.identity_runtime_config import (
    UNSAFE_CONDITIONS,
    IdentityConfigResult,
    validate_identity_runtime_config,
)
from shared.sdk.identity.role_mapping import (
    is_wildcard_group,
    load_policy,
    load_rules,
    load_safe_fixture,
    map_identity_to_role,
    validate_rules,
)
from shared.sdk.identity.role_mapping_models import (
    IdentityClaims,
    RoleMappingDecision,
    RoleMappingRule,
)
from shared.sdk.identity.session_cleanup import CleanupPlan, plan_cleanup, run_cleanup

__all__ = [
    "ALLOWED_ROLES",
    "OidcClaimContract",
    "OidcConfigStatus",
    "OidcProviderConfig",
    "SecretRef",
    "OidcValidationResult",
    "load_oidc_config",
    "validate_oidc_inputs",
    "REQUIRED_POLICY_KEYS",
    "load_oidc_policies",
    "policy_keys",
    "OidcProvider",
    "OidcProviderError",
    "OidcDisabledError",
    "contains_secret_like",
    "find_secret_like",
    "IdentityConfigResult",
    "validate_identity_runtime_config",
    "UNSAFE_CONDITIONS",
    "IdentityClaims",
    "RoleMappingDecision",
    "RoleMappingRule",
    "map_identity_to_role",
    "validate_rules",
    "is_wildcard_group",
    "load_rules",
    "load_policy",
    "load_safe_fixture",
    "CleanupPlan",
    "plan_cleanup",
    "run_cleanup",
]
