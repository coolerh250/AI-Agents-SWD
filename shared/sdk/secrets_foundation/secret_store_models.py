"""Step 53 -- secret store abstraction models (no value, no network)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SecretMetadata(BaseModel):
    """Non-sensitive metadata about a referenced secret. NEVER the value."""

    model_config = ConfigDict(extra="forbid")

    store: str
    name: str
    key: str
    configured: bool
    production_ready: bool
    version: str | None = None


class SecretValueAccessDisabledError(RuntimeError):
    """Raised whenever a live secret VALUE read is attempted in this stage."""


__all__ = ["SecretMetadata", "SecretValueAccessDisabledError"]
