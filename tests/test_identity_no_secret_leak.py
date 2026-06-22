"""Step 52.1 -- no secret / token leak in identity files."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENT = ROOT / "infra" / "identity"
SECRET = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|"
    r"(client_secret|clientsecret|signing_secret|refresh_token|password|cookie_secret)\s*[:=]\s*[A-Za-z0-9/+=._-]{6,})",
    re.IGNORECASE,
)
REAL_OIDC = re.compile(
    r"(jwks_uri\s*[:=]\s*http|issuer\s*[:=]\s*https?://[a-z0-9.-]+\.[a-z])", re.IGNORECASE
)


def test_no_secret_like_value() -> None:
    for p in IDENT.glob("*.yaml"):
        for ln in p.read_text(encoding="utf-8").splitlines():
            assert not SECRET.search(ln), f"{p.name}: {ln.strip()[:60]}"


def test_no_real_oidc_endpoint() -> None:
    for p in IDENT.glob("*.yaml"):
        assert not REAL_OIDC.search(p.read_text(encoding="utf-8")), p.name


def test_no_jwt_blob() -> None:
    jwt = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
    for p in IDENT.glob("*.yaml"):
        assert not jwt.search(p.read_text(encoding="utf-8")), p.name
