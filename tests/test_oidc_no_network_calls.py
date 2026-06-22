"""Step 52.2 -- OIDC abstraction performs no network call.

The identity SDK must not import an HTTP client, and every live provider
operation must fail closed with ``OidcDisabledError``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.sdk.identity import OidcDisabledError, OidcProvider, OidcProviderConfig

ROOT = Path(__file__).resolve().parents[1]
SDK_DIR = ROOT / "shared" / "sdk" / "identity"
_HTTP_IMPORTS = (
    "import requests",
    "import httpx",
    "import aiohttp",
    "from requests",
    "from httpx",
    "from aiohttp",
)


def test_no_http_client_import_in_sdk() -> None:
    for p in SDK_DIR.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            assert not stripped.startswith(_HTTP_IMPORTS), f"{p.name}: {stripped}"


def test_provider_operations_fail_closed() -> None:
    p = OidcProvider(OidcProviderConfig(provider_key="production-oidc-placeholder"))
    assert p.is_enabled() is False
    with pytest.raises(OidcDisabledError):
        p.fetch_discovery()
    with pytest.raises(OidcDisabledError):
        p.fetch_jwks()
    with pytest.raises(OidcDisabledError):
        p.exchange_code("code", state="s", nonce="n")
    with pytest.raises(OidcDisabledError):
        p.validate_id_token("token", nonce="n")
