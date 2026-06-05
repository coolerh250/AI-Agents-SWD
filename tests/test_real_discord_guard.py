"""Stage 32 -- Discord real-pilot guard unit tests."""

from __future__ import annotations

from shared.sdk.real_integration import (
    evaluate_real_discord_request,
    render_safe_discord_message,
)


def _good_env() -> dict[str, str]:
    return {
        "DISCORD_BOT_TOKEN": "fake-bot-token",
        "DISCORD_TEST_GUILD_ID": "g123",
        "DISCORD_TEST_CHANNEL_ID": "c456",
        "RUN_REAL_DISCORD_TEST": "true",
    }


def test_valid_request_allowed():
    res = evaluate_real_discord_request(channel_id="c456", guild_id="g123", env=_good_env())
    assert res.allowed is True
    assert res.target_channel == "c456"
    assert res.mode == "controlled_test"


def test_missing_token_blocked():
    env = _good_env()
    env.pop("DISCORD_BOT_TOKEN")
    res = evaluate_real_discord_request(channel_id="c456", env=env)
    assert res.allowed is False
    assert res.reason == "missing_discord_bot_token"


def test_opt_in_not_true_blocked():
    env = _good_env()
    env["RUN_REAL_DISCORD_TEST"] = "false"
    res = evaluate_real_discord_request(channel_id="c456", env=env)
    assert res.allowed is False
    assert res.reason == "run_real_discord_test_not_true"


def test_wrong_channel_blocked():
    res = evaluate_real_discord_request(channel_id="some-other-channel", env=_good_env())
    assert res.allowed is False
    assert res.reason == "channel_not_test_channel"


def test_wrong_guild_blocked():
    res = evaluate_real_discord_request(channel_id="c456", guild_id="g-different", env=_good_env())
    assert res.allowed is False
    assert res.reason == "guild_not_test_guild"


def test_role_not_allowed_when_pinned():
    env = _good_env()
    env["DISCORD_ALLOWED_ROLE_ID"] = "r-allow"
    res = evaluate_real_discord_request(
        channel_id="c456", guild_id="g123", role_id="r-other", env=env
    )
    assert res.allowed is False
    assert res.reason == "role_not_allowed"


def test_role_optional_when_unset():
    res = evaluate_real_discord_request(
        channel_id="c456", guild_id="g123", role_id="r-something", env=_good_env()
    )
    assert res.allowed is True


def test_mode_must_be_controlled_test():
    res = evaluate_real_discord_request(
        channel_id="c456", guild_id="g123", mode="production_send", env=_good_env()
    )
    assert res.allowed is False
    assert res.reason == "mode_not_controlled_test"


def test_production_executed_must_be_false_literal():
    res = evaluate_real_discord_request(
        channel_id="c456", guild_id="g123", production_executed=None, env=_good_env()
    )
    assert res.allowed is False
    assert res.reason == "production_executed_not_false"


def test_safe_dict_carries_no_token():
    res = evaluate_real_discord_request(channel_id="c456", env=_good_env())
    safe = res.to_safe_dict()
    assert "fake-bot-token" not in repr(safe).lower()


# ----- render_safe_discord_message -----


def test_render_only_whitelisted_fields():
    body = render_safe_discord_message(
        summary="hello",
        fields={
            "task_id": "t-1",
            "status": "controlled_test",
            "operations_url": "/operations/workflows/t-1",
            "internal_field": "should-not-appear",
            "DATABASE_URL": "postgres://secret@x",
        },
    )
    assert "hello" in body
    assert "task_id: t-1" in body
    assert "status: controlled_test" in body
    assert "internal_field" not in body
    assert "DATABASE_URL" not in body
    assert "postgres://secret" not in body


def test_render_redacts_token_shapes():
    body = render_safe_discord_message(
        summary="paste ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA accidentally",
        fields={"task_id": "t", "status": "x", "operations_url": "/"},
    )
    assert "ghp_AAAAA" not in body
    assert "REDACTED" in body


def test_render_prefixes_sandbox_marker():
    body = render_safe_discord_message(summary="hi", fields={"task_id": "t"})
    assert body.startswith("[AI-Agents-SWD sandbox]")
