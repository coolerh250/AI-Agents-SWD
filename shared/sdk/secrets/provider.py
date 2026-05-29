"""SecretProvider — env-backed default, Vault placeholder ready.

The Stage 24 baseline lets every caller go through one entry point:

    from shared.sdk.secrets import default_provider
    token = default_provider().get_secret("GITHUB_TOKEN")
    if token:                              # SecretRef.__bool__
        headers["Authorization"] = f"Bearer {token.reveal()}"

The Vault provider in this file is a placeholder. It satisfies the
interface and returns ``SecretRef(present=False)`` for every lookup, so
production code can register a real Vault client later without touching
any call site.
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, Mapping

from shared.sdk.secrets.models import REDACTION_TOKEN, SecretRef

# Substring match (case-insensitive) on env-var / dict key names. Any
# key that contains one of these is treated as secret-shaped — the
# value is redacted by ``redact_mapping``.
_SECRET_KEY_HINTS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "credential",
    "private_key",
)

_PLACEHOLDER_MARKER = "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"


def _is_secret_key(key: str) -> bool:
    key_lower = (key or "").lower()
    return any(hint in key_lower for hint in _SECRET_KEY_HINTS)


def redact(value: Any) -> str:
    """Render any value as ``***REDACTED***``.

    The helper is intentionally lossy — callers should never log a
    secret. The function returns the redaction token unconditionally
    so it's safe to drop into log lines / audit rows / response bodies.
    """
    if value is None or value == "":
        return ""
    return REDACTION_TOKEN


def redact_mapping(mapping: Mapping[str, Any], *, extra_keys: Iterable[str] = ()) -> dict[str, Any]:
    """Return a new dict with every secret-shaped key redacted.

    ``extra_keys`` allows the caller to opt-in additional names that
    don't match the default substring heuristic (e.g. project-specific
    aliases).
    """
    extras = {k.lower() for k in extra_keys}
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        key_l = (key or "").lower()
        if _is_secret_key(key) or key_l in extras:
            out[key] = REDACTION_TOKEN if value else value
        else:
            out[key] = value
    return out


class SecretProvider:
    """Abstract base. Concrete providers must implement :meth:`_lookup`."""

    name = "abstract"

    def get_secret(self, name: str) -> SecretRef:
        raw = self._lookup(name)
        if raw is None:
            return SecretRef(name=name, present=False)
        stripped = raw.strip()
        if not stripped or stripped == _PLACEHOLDER_MARKER:
            # Placeholders never count as "present". The validator
            # treats placeholder values as a Stage 24 failure for
            # staging / production-check modes.
            return SecretRef(name=name, present=False)
        return SecretRef(name=name, _value=stripped, present=True)

    def has_secret(self, name: str) -> bool:
        return self.get_secret(name).present

    def _lookup(self, name: str) -> str | None:
        raise NotImplementedError


class EnvSecretProvider(SecretProvider):
    """Read secrets from a snapshot of ``os.environ`` (or a passed dict).

    Tests use the ``env`` kwarg to inject a fixed dict. Production code
    passes nothing and reads the live process environment at call time.
    """

    name = "env"

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = env if env is not None else os.environ

    def _lookup(self, name: str) -> str | None:
        try:
            return self._env.get(name)
        except Exception:
            return None


class VaultPlaceholderProvider(SecretProvider):
    """Stage 24 placeholder. Returns ``None`` for every lookup.

    Real Vault wiring lives in a future stage. The class exists so
    code can construct it today, write tests against the interface,
    and swap in a real client later without changing any call site.
    """

    name = "vault-placeholder"

    def __init__(self, vault_addr: str | None = None) -> None:
        # Recorded so a future provider can drop in. The address is
        # NOT a secret — it's the URL of the Vault server.
        self.vault_addr = vault_addr or os.environ.get("VAULT_ADDR", "")

    def _lookup(self, name: str) -> str | None:  # noqa: ARG002
        return None


_DEFAULT_PROVIDER: SecretProvider | None = None


def default_provider() -> SecretProvider:
    """Return the singleton EnvSecretProvider.

    Tests reset the singleton by importing this module and clearing
    ``_DEFAULT_PROVIDER``; production code just calls the function.
    """
    global _DEFAULT_PROVIDER
    if _DEFAULT_PROVIDER is None:
        _DEFAULT_PROVIDER = EnvSecretProvider()
    return _DEFAULT_PROVIDER


# Detection helper used by the validator + tests to fail loudly when a
# placeholder slips into a "live" env.
_PLACEHOLDER_REGEX = re.compile(re.escape(_PLACEHOLDER_MARKER))


def looks_like_placeholder(value: str | None) -> bool:
    if not value:
        return False
    return bool(_PLACEHOLDER_REGEX.search(value))
