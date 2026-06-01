"""Stage 26 — secrets inventory YAML + lister script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_INVENTORY = _REPO_ROOT / "infra" / "runtime" / "secrets.inventory.yml"
_LIST_SCRIPT = _REPO_ROOT / "scripts" / "list_required_secrets.py"

REQUIRED_NAMES = {
    "POSTGRES_PASSWORD",
    "GITHUB_TOKEN",
    "DISCORD_BOT_TOKEN",
    "DISCORD_TEST_CHANNEL_ID",
    "ALERTMANAGER_WEBHOOK_URL",
    "VAULT_TOKEN",
    "VAULT_ADDR",
}


def _load_yaml() -> dict:
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(_INVENTORY.read_text(encoding="utf-8"))


def test_inventory_file_exists():
    assert _INVENTORY.is_file()


def test_inventory_contains_required_names():
    doc = _load_yaml()
    names = {entry["name"] for entry in doc["secrets"]}
    missing = REQUIRED_NAMES - names
    assert not missing, f"inventory missing: {missing}"


def test_inventory_has_no_real_token_substring():
    text = _INVENTORY.read_text(encoding="utf-8")
    for pattern in ("ghp_", "github_pat_", "xoxb-", "sk-"):
        # Allow the prefix to appear inside notes describing the pattern,
        # but never followed by a long token-shape body.
        import re

        if pattern == "ghp_":
            assert not re.search(r"ghp_[A-Za-z0-9_]{16,}", text)
        elif pattern == "github_pat_":
            assert not re.search(r"github_pat_[A-Za-z0-9_]{16,}", text)
        elif pattern == "xoxb-":
            assert not re.search(r"xoxb-[A-Za-z0-9-]{8,}", text)
        elif pattern == "sk-":
            assert not re.search(r"sk-[A-Za-z0-9]{20,}", text)


def test_inventory_entries_have_required_fields():
    doc = _load_yaml()
    required = {
        "name",
        "required_for",
        "environments",
        "provider",
        "rotation_policy",
        "allowed_to_be_missing_in_local",
        "allowed_to_be_missing_in_staging",
        "leak_risk",
    }
    for entry in doc["secrets"]:
        missing = required - set(entry.keys())
        assert not missing, f"{entry.get('name')} missing fields: {missing}"


def test_inventory_leak_risk_is_known_band():
    doc = _load_yaml()
    allowed = {"low", "medium", "high", "critical"}
    for entry in doc["secrets"]:
        assert entry["leak_risk"] in allowed, entry["name"]


def test_inventory_provider_per_env_uses_supported_names():
    doc = _load_yaml()
    allowed = {"env", "vault", "mock-vault"}
    for entry in doc["secrets"]:
        provider_map = entry.get("provider") or {}
        for env_name, prov in provider_map.items():
            assert prov in allowed, f"{entry['name']}.provider.{env_name}={prov} not in {allowed}"


def test_list_required_secrets_script_passes_default():
    res = subprocess.run(
        [sys.executable, str(_LIST_SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "REQUIRED_SECRETS_INVENTORY: PASS" in res.stdout


def test_list_required_secrets_script_json_mode():
    res = subprocess.run(
        [sys.executable, str(_LIST_SCRIPT), "--json"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    parsed = json.loads(res.stdout)
    assert parsed["passed"] is True
    assert parsed["count"] >= 7
    names = {row["name"] for row in parsed["secrets"]}
    assert REQUIRED_NAMES.issubset(names)
    # values must not appear anywhere in the JSON shape (only names/types)
    serialised = json.dumps(parsed)
    for tok in ("ghp_", "github_pat_", "xoxb-", "sk-real"):
        # Re-check after serialisation as a final guard.
        if tok == "ghp_":
            import re

            assert not re.search(r"ghp_[A-Za-z0-9_]{16,}", serialised)
        elif tok == "github_pat_":
            import re

            assert not re.search(r"github_pat_[A-Za-z0-9_]{16,}", serialised)
