"""Stage 26 — MockVaultSecretProvider file-backed reads."""

from __future__ import annotations

import json
from pathlib import Path

from shared.sdk.secrets import MockVaultSecretProvider, SecretRef


def test_mock_vault_missing_file_returns_absent(tmp_path: Path):
    target = tmp_path / "missing.json"
    p = MockVaultSecretProvider(path=target)
    assert p.get_secret("X").present is False
    assert p.status["mock_file_present"] is False
    assert p.status["last_error"] == "mock_file_missing"


def test_mock_vault_reads_flat_json(tmp_path: Path):
    target = tmp_path / "v.json"
    target.write_text(
        json.dumps({"POSTGRES_PASSWORD": "secret-A", "GITHUB_TOKEN": "fake"}),
        encoding="utf-8",
    )
    p = MockVaultSecretProvider(path=target)
    pw = p.get_secret("POSTGRES_PASSWORD")
    assert pw.present is True
    assert pw.reveal() == "secret-A"
    assert isinstance(pw, SecretRef)


def test_mock_vault_rotation_through_reload(tmp_path: Path):
    target = tmp_path / "v.json"
    target.write_text(json.dumps({"K": "A"}), encoding="utf-8")
    p = MockVaultSecretProvider(path=target)
    assert p.get_secret("K").reveal() == "A"
    target.write_text(json.dumps({"K": "B"}), encoding="utf-8")
    assert p.get_secret("K").reveal() == "A"  # cached
    p.reload()
    assert p.get_secret("K").reveal() == "B"


def test_mock_vault_refuses_real_github_token_shape(tmp_path: Path):
    target = tmp_path / "v.json"
    target.write_text(
        json.dumps(
            {
                "GITHUB_TOKEN": "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "POSTGRES_PASSWORD": "ok-pw",
            }
        ),
        encoding="utf-8",
    )
    p = MockVaultSecretProvider(path=target)
    assert p.get_secret("GITHUB_TOKEN").present is False
    # POSTGRES_PASSWORD is still readable.
    assert p.get_secret("POSTGRES_PASSWORD").reveal() == "ok-pw"


def test_mock_vault_allow_real_shapes_opt_in(tmp_path: Path):
    target = tmp_path / "v.json"
    target.write_text(
        json.dumps({"GITHUB_TOKEN": "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAA"}),
        encoding="utf-8",
    )
    p = MockVaultSecretProvider(path=target, allow_real_token_shapes=True)
    assert p.get_secret("GITHUB_TOKEN").present is True


def test_mock_vault_list_returns_names_only(tmp_path: Path):
    target = tmp_path / "v.json"
    target.write_text(json.dumps({"K1": "v1-NEVER-EXPOSE", "K2": "v2"}), encoding="utf-8")
    p = MockVaultSecretProvider(path=target)
    names = p.list_available_secrets()
    assert sorted(names) == ["K1", "K2"]
    serialised = repr(names)
    assert "v1-NEVER-EXPOSE" not in serialised


def test_mock_vault_status_never_carries_value(tmp_path: Path):
    target = tmp_path / "v.json"
    target.write_text(json.dumps({"K": "NEVER-EXPOSE-VALUE"}), encoding="utf-8")
    p = MockVaultSecretProvider(path=target)
    p.get_secret("K")  # populate cache
    status = p.status
    assert "NEVER-EXPOSE-VALUE" not in repr(status)
    assert status["mock_file_present"] is True
    assert status["secret_count"] == 1


def test_mock_vault_placeholder_marker_is_absent(tmp_path: Path):
    target = tmp_path / "v.json"
    target.write_text(
        json.dumps({"K": "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"}),
        encoding="utf-8",
    )
    p = MockVaultSecretProvider(path=target)
    assert p.get_secret("K").present is False


def test_mock_vault_corrupt_json_safe(tmp_path: Path):
    target = tmp_path / "v.json"
    target.write_text("{not json", encoding="utf-8")
    p = MockVaultSecretProvider(path=target)
    assert p.get_secret("K").present is False
    assert "parse_error" in p.status["last_error"]
