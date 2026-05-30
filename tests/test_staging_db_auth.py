"""Stage 25 staging DB auth contract checks.

The staging compose must NOT enable Postgres trust auth. Every consumer
service that reads DATABASE_URL must interpolate the password through
docker compose's env-var substitution; the password value lives only
in ``infra/runtime/.env.staging.local`` (gitignored).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None  # type: ignore[assignment]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STAGING = _REPO_ROOT / "infra" / "docker-compose" / "docker-compose.staging.yml"
_LOCAL = _REPO_ROOT / "infra" / "docker-compose" / "docker-compose.yml"
_EXAMPLE = _REPO_ROOT / "infra" / "runtime" / "env.staging.example"


def _load_yaml(path: Path) -> dict:
    if _yaml is None:
        pytest.skip("PyYAML not installed")
    return _yaml.safe_load(path.read_text(encoding="utf-8"))


def test_staging_postgres_no_trust_auth_env():
    doc = _load_yaml(_STAGING)
    env = (doc["services"]["postgres"]).get("environment") or {}
    assert "POSTGRES_HOST_AUTH_METHOD" not in env
    # Defensive substring check too.
    assert "POSTGRES_HOST_AUTH_METHOD: trust" not in _STAGING.read_text(encoding="utf-8")


def test_staging_postgres_password_required_form():
    text = _STAGING.read_text(encoding="utf-8")
    # The ${VAR:?msg} form makes compose refuse to start without the
    # password. Plain ${VAR} or ${VAR:-default} is NOT sufficient.
    assert re.search(r"POSTGRES_PASSWORD: \$\{POSTGRES_PASSWORD:\?[^}]+\}", text)


def test_staging_database_url_uses_password():
    """Every staging service's DATABASE_URL must carry the
    ${POSTGRES_PASSWORD} substitution token.
    """
    doc = _load_yaml(_STAGING)
    services = doc.get("services") or {}
    db_users = [
        name
        for name, block in services.items()
        if isinstance(block.get("environment"), dict) and "DATABASE_URL" in block["environment"]
    ]
    assert len(db_users) >= 10, "expected most services to declare DATABASE_URL"
    for name in db_users:
        url = str(services[name]["environment"]["DATABASE_URL"])
        assert "${POSTGRES_PASSWORD}" in url, f"{name} DATABASE_URL missing password"
        assert "@postgres:5432" in url, f"{name} DATABASE_URL missing host:port"


def test_staging_postgres_user_is_not_postgres_superuser_alias():
    """The local cluster uses ``postgres`` (the default superuser). The
    staging cluster uses a distinct ``aiagents_app`` user that owns
    the DB but is created via the standard Postgres init flow.
    """
    text = _STAGING.read_text(encoding="utf-8")
    assert "STAGING_POSTGRES_USER:-aiagents_app" in text


def test_local_compose_keeps_trust_auth_unchanged():
    """Regression guard — the local file must keep trust auth so the
    existing cluster on 10.0.1.31 boots without a password."""
    doc = _load_yaml(_LOCAL)
    env = (doc["services"]["postgres"]).get("environment") or {}
    assert env.get("POSTGRES_HOST_AUTH_METHOD") == "trust"


def test_env_example_postgres_password_is_placeholder():
    text = _EXAMPLE.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE" in text


def test_no_secret_committed_in_staging_compose():
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    assert forbidden.search(_STAGING.read_text(encoding="utf-8")) is None
    assert forbidden.search(_EXAMPLE.read_text(encoding="utf-8")) is None
