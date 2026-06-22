"""Step 53 -- reference-only SecretRef (no value, ever).

Distinct from ``shared.sdk.secrets.SecretRef`` (a runtime value-holder). This
model describes only WHERE a secret lives -- never the value. The validator
rejects any field that looks like an inline secret (value/secret/token/password/
client_secret literal, JWT, private key block).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

SecretStore = Literal[
    "disabled",
    "external_secret_store",
    "kubernetes_secret_ref",
    "vault_ref",
    "gcp_secret_manager_ref",
    "aws_secrets_manager_ref",
    "azure_key_vault_ref",
]

# Inline-value shapes that must never appear in a reference's name/key.
_INLINE_VALUE = re.compile(
    r"(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.|BEGIN [A-Z ]*PRIVATE KEY|"
    r"ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"(client_secret|password|secret_value|api_key)\s*[:=]\s*\S{6,})",
    re.IGNORECASE,
)
_FORBIDDEN_FIELDS = ("value", "secret", "token", "password", "client_secret")


class SecretRef(BaseModel):
    """A pointer to a secret in a store. Carries NO secret value."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    store: SecretStore = "disabled"
    name: str = ""
    key: str = ""
    version: str | None = None
    required: bool = False
    production_allowed: bool = False

    @field_validator("name", "key", "version")
    @classmethod
    def _no_inline_value(cls, v: str | None) -> str | None:
        if v and _INLINE_VALUE.search(v):
            raise ValueError("SecretRef must not contain an inline secret value")
        return v

    @property
    def configured(self) -> bool:
        return self.store != "disabled" and bool(self.name and self.key)

    @property
    def production_ready(self) -> bool:
        """A reference is production-ready only if it is fully configured AND
        explicitly production-allowed AND not on the disabled store."""
        return self.configured and self.production_allowed and self.store != "disabled"


def validate_ref_dict(data: dict) -> list[str]:
    """Return reasons a raw reference dict is unsafe (inline value / bad field)."""
    errors: list[str] = []
    for forbidden in _FORBIDDEN_FIELDS:
        if forbidden in data and forbidden not in ("name", "key"):
            # an explicit 'value'/'secret'/'token'/'password'/'client_secret' field
            errors.append(f"reference must not carry a {forbidden!r} field")
    for k, val in data.items():
        if isinstance(val, str) and _INLINE_VALUE.search(val):
            errors.append(f"inline secret value in field {k!r}")
    return errors


__all__ = ["SecretStore", "SecretRef", "validate_ref_dict"]
