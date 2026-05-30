"""Stage 24 static checks for infra/docker-compose/docker-compose.staging.yml.

The staging template MUST:
  * not include POSTGRES_HOST_AUTH_METHOD=trust
  * reference POSTGRES_PASSWORD via env-var substitution
  * not embed real secret values
  * use a different volume name from the local/test compose
  * not start the dev-mode Vault container

The test does NOT actually launch the template — it only parses the YAML.
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


def _load_yaml(path: Path) -> dict:
    if _yaml is None:
        pytest.skip("PyYAML not installed")
    return _yaml.safe_load(path.read_text(encoding="utf-8"))


def test_staging_template_exists():
    assert _STAGING.is_file()


def test_staging_template_no_trust_auth():
    text = _STAGING.read_text(encoding="utf-8")
    assert "POSTGRES_HOST_AUTH_METHOD: trust" not in text
    assert (
        "POSTGRES_HOST_AUTH_METHOD" not in text
        or re.search(r"POSTGRES_HOST_AUTH_METHOD: \w+", text) is None
        or "trust" not in text
    )


def test_staging_template_password_via_env():
    text = _STAGING.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD" in text


def test_staging_template_no_real_secret_bytes():
    text = _STAGING.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    assert forbidden.search(text) is None


def test_staging_template_uses_separate_volume():
    doc = _load_yaml(_STAGING)
    volumes = doc.get("volumes") or {}
    assert "postgres-staging-data" in volumes


def test_staging_template_vault_dev_mode_documented_as_escape_hatch():
    """Stage 25 expanded the staging template to a full 22-service stack
    and explicitly included the dev-mode vault container behind the
    documented ``ALLOW_VAULT_DEV_MODE_FOR_STAGING=true`` escape hatch.

    The validator's ``staging`` mode rejects vault dev-mode unless the
    escape hatch is set (covered by
    ``test_runtime_config_validator.test_staging_vault_dev_mode_*``).
    The compose file itself must call this out in a comment so an
    operator reading the YAML can see the limitation in-place.
    """
    text = _STAGING.read_text(encoding="utf-8")
    assert "ALLOW_VAULT_DEV_MODE_FOR_STAGING" in text
    doc = _load_yaml(_STAGING)
    if "vault" in (doc.get("services") or {}):
        # If the dev-mode vault is included, the template MUST mention
        # the escape hatch + the fact that it's a documented limitation.
        assert "staging limitation" in text.lower() or "escape hatch" in text.lower()


def test_staging_template_name_distinct_from_local():
    doc = _load_yaml(_STAGING)
    assert doc.get("name") == "aiagents-staging"


def test_local_compose_still_uses_trust_auth():
    """The Stage 24 deliverable is ADDITIVE — the local cluster keeps
    its existing trust-auth posture so docker-compose.yml behaviour
    doesn't change. If this assertion ever flips false, the local
    cluster has been broken by the staging hardening work.
    """
    text = _LOCAL.read_text(encoding="utf-8")
    assert "POSTGRES_HOST_AUTH_METHOD: trust" in text
