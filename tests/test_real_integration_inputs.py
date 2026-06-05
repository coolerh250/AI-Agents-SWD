"""Stage 32 -- real-integration operator-input snapshot tests."""

from __future__ import annotations

from shared.sdk.real_integration import collect_real_integration_inputs


def _empty_env() -> dict[str, str]:
    return {}


def test_empty_env_marks_nothing_ready():
    snap = collect_real_integration_inputs(_empty_env())
    assert snap["discord_required_present"] is False
    assert snap["discord_opt_in_active"] is False
    assert snap["discord_ready"] is False
    assert snap["github_required_present"] is False
    assert snap["github_opt_in_active"] is False
    assert snap["github_ready"] is False
    assert snap["no_token_leak"] is True
    # entries carry only booleans + lengths, never values
    for entry in snap["discord"] + snap["github"]:
        assert "value" not in entry
        assert entry["length"] == 0


def test_discord_optional_role_does_not_block_readiness():
    env = {
        "DISCORD_BOT_TOKEN": "fake",
        "DISCORD_TEST_GUILD_ID": "1",
        "DISCORD_TEST_CHANNEL_ID": "2",
        "RUN_REAL_DISCORD_TEST": "true",
    }
    snap = collect_real_integration_inputs(env)
    assert snap["discord_required_present"] is True
    assert snap["discord_opt_in_active"] is True
    assert snap["discord_ready"] is True


def test_discord_missing_channel_blocks_ready():
    env = {
        "DISCORD_BOT_TOKEN": "fake",
        "DISCORD_TEST_GUILD_ID": "1",
        "RUN_REAL_DISCORD_TEST": "true",
    }
    snap = collect_real_integration_inputs(env)
    assert snap["discord_ready"] is False
    assert snap["discord_required_present"] is False


def test_discord_opt_in_must_be_true_literal():
    env = {
        "DISCORD_BOT_TOKEN": "fake",
        "DISCORD_TEST_GUILD_ID": "1",
        "DISCORD_TEST_CHANNEL_ID": "2",
        "RUN_REAL_DISCORD_TEST": "yes",
    }
    snap = collect_real_integration_inputs(env)
    assert snap["discord_opt_in_active"] is False
    assert snap["discord_ready"] is False


def test_github_full_env_marks_ready():
    env = {
        "GITHUB_TOKEN": "fake",
        "GITHUB_TEST_REPO": "owner/sandbox-repo",
        "RUN_REAL_GITHUB_TEST": "true",
    }
    snap = collect_real_integration_inputs(env)
    assert snap["github_required_present"] is True
    assert snap["github_opt_in_active"] is True
    assert snap["github_ready"] is True


def test_github_missing_repo_blocks_ready():
    env = {"GITHUB_TOKEN": "x", "RUN_REAL_GITHUB_TEST": "true"}
    snap = collect_real_integration_inputs(env)
    assert snap["github_ready"] is False


def test_snapshot_never_copies_token_value():
    env = {
        "DISCORD_BOT_TOKEN": "secret-bot-token",
        "DISCORD_TEST_GUILD_ID": "g",
        "DISCORD_TEST_CHANNEL_ID": "c",
        "RUN_REAL_DISCORD_TEST": "true",
        "GITHUB_TOKEN": "ghp_secret",
    }
    snap = collect_real_integration_inputs(env)
    raw = repr(snap)
    assert "secret-bot-token" not in raw
    assert "ghp_secret" not in raw
