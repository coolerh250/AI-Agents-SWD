"""Step 52.2 -- OIDC provider abstraction (interface only, NO network).

This defines the provider surface a future production step would implement.
Every operation that would require an external IdP -- discovery, JWKS fetch,
authorization-code exchange, ID-token validation -- raises ``OidcDisabledError``
in this step. There is NO concrete provider that talks to a network.
"""

from __future__ import annotations

from shared.sdk.identity.oidc_models import OidcProviderConfig


class OidcProviderError(RuntimeError):
    """Base error for the OIDC abstraction."""


class OidcDisabledError(OidcProviderError):
    """Raised whenever a real OIDC operation is attempted while disabled."""


class OidcProvider:
    """Abstract provider. In Step 52.2 every live operation fails closed.

    The methods exist so the future production step has a stable contract, but
    none performs a network call, parses a real token, or creates a session.
    """

    def __init__(self, config: OidcProviderConfig) -> None:
        self.config = config

    def is_enabled(self) -> bool:
        return bool(self.config.enabled and self.config.production_allowed)

    def fetch_discovery(self) -> dict[str, object]:
        raise OidcDisabledError("OIDC discovery fetch is disabled in Step 52.2")

    def fetch_jwks(self) -> dict[str, object]:
        raise OidcDisabledError("JWKS fetch is disabled in Step 52.2")

    def exchange_code(self, code: str, *, state: str, nonce: str) -> dict[str, object]:
        raise OidcDisabledError("Authorization-code exchange is disabled in Step 52.2")

    def validate_id_token(self, token: str, *, nonce: str) -> dict[str, object]:
        raise OidcDisabledError("ID-token validation is disabled in Step 52.2")


__all__ = ["OidcProviderError", "OidcDisabledError", "OidcProvider"]
