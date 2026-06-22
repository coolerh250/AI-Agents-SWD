"""Step 53 -- production secret management foundation (modeled, fail-closed).

Read-only aggregation of the committed infra/secrets catalogs into a redacted
posture for the read-only operations API, /operations/safety, and the Admin
Console Secret Posture view. NEVER connects to a secret store, reads a secret
value, reads a runtime key file, or enables production auth/deploy.

Distinct from ``shared.sdk.secrets`` (the runtime value-holding provider). The
``SecretRef`` here is reference-only and carries no value.
"""

from __future__ import annotations

from shared.sdk.secrets_foundation.collector import (
    LIMITATIONS,
    NEXT_REQUIRED_STEPS,
    STATUS_FAILED,
    STATUS_MODELED,
    STATUS_UNKNOWN,
    build_secret_foundation_summary,
    collect_secret_posture,
    load_secret_foundation_summary,
)
from shared.sdk.secrets_foundation.report_builder import (
    foundation_view,
    full_report,
    load_summary,
    readiness_view,
    section,
)
from shared.sdk.secrets_foundation.safety import secret_safety_fields
from shared.sdk.secrets_foundation.secret_policy import (
    SECRET_CLASSES,
    class_of,
    load_classification,
    load_redaction_policy,
)
from shared.sdk.secrets_foundation.secret_redaction import (
    REDACTION_TOKEN,
    contains_committed_secret,
    find_committed_secret,
    redact,
)
from shared.sdk.secrets_foundation.secret_ref import SecretRef, SecretStore, validate_ref_dict
from shared.sdk.secrets_foundation.secret_store import (
    DisabledSecretStoreProvider,
    SecretMetadata,
    SecretStoreProvider,
    SecretValueAccessDisabledError,
)

__all__ = [
    "LIMITATIONS",
    "NEXT_REQUIRED_STEPS",
    "STATUS_FAILED",
    "STATUS_MODELED",
    "STATUS_UNKNOWN",
    "build_secret_foundation_summary",
    "collect_secret_posture",
    "load_secret_foundation_summary",
    "foundation_view",
    "full_report",
    "load_summary",
    "readiness_view",
    "section",
    "secret_safety_fields",
    "SECRET_CLASSES",
    "class_of",
    "load_classification",
    "load_redaction_policy",
    "REDACTION_TOKEN",
    "contains_committed_secret",
    "find_committed_secret",
    "redact",
    "SecretRef",
    "SecretStore",
    "validate_ref_dict",
    "DisabledSecretStoreProvider",
    "SecretMetadata",
    "SecretStoreProvider",
    "SecretValueAccessDisabledError",
]
