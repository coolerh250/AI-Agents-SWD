"""Stage 33 -- pure-policy tests for shared.sdk.notifications.real_delivery_policy.

The module is pure: no I/O, no env mutation, no audit publish. These
tests pin down every decision branch + the redaction guarantee that
no token value ever ends up in the result dict.
"""

from __future__ import annotations

from shared.sdk.notifications.real_delivery_policy import (
    DELIVERY_DECISION_REAL_ALLOWED,
    DELIVERY_DECISION_REAL_BLOCKED,
    DELIVERY_DECISION_SIMULATED,
    DELIVERY_DECISION_SKIPPED,
    REASON_EVENT_DENIED,
    REASON_EVENT_NOT_ALLOWED,
    REASON_MISSING_MARKER,
    REASON_PRODUCTION_EXECUTED,
    REASON_REAL_MODE_DISABLED,
    REASON_TOKEN_MISSING,
    REASON_WRONG_CHANNEL,
    RealDeliveryPolicy,
    classify_real_delivery,
    load_policy_from_env,
)


def _enabled_policy(**overrides):
    base = {
        "real_mode_enabled": True,
        "allowlist": ["discord.real_test_sent", "discord.real_task_received"],
        "denylist": ["workflow.*", "qa.*", "code.*", "github.*", "task.*"],
        "allow_marker": True,
        "test_channel_id": "C-TEST",
    }
    base.update(overrides)
    return RealDeliveryPolicy(**base)


def test_sandbox_when_real_mode_disabled():
    policy = _enabled_policy(real_mode_enabled=False)
    decision = classify_real_delivery({"event_type": "workflow.completed"}, policy)
    assert decision.decision == DELIVERY_DECISION_SIMULATED
    assert decision.reason == REASON_REAL_MODE_DISABLED
    assert decision.external_sent is False
    assert decision.sandbox is True


def test_skipped_when_test_channel_missing():
    policy = _enabled_policy(test_channel_id="")
    decision = classify_real_delivery({"event_type": "discord.real_test_sent"}, policy)
    assert decision.decision == DELIVERY_DECISION_SKIPPED
    assert decision.reason == REASON_TOKEN_MISSING


def test_internal_event_blocked_by_default():
    policy = _enabled_policy()
    decision = classify_real_delivery({"event_type": "workflow.completed"}, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_EVENT_DENIED


def test_qa_event_blocked_by_default():
    policy = _enabled_policy()
    decision = classify_real_delivery({"event_type": "qa.validation_passed"}, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_EVENT_DENIED


def test_code_event_blocked_by_default():
    policy = _enabled_policy()
    decision = classify_real_delivery({"event_type": "code.generated"}, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_EVENT_DENIED


def test_github_event_blocked_by_default():
    policy = _enabled_policy()
    decision = classify_real_delivery({"event_type": "github.sandbox_pr.created"}, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_EVENT_DENIED


def test_explicit_real_event_allowed():
    policy = _enabled_policy()
    decision = classify_real_delivery({"event_type": "discord.real_test_sent"}, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_ALLOWED
    assert decision.target_channel == "C-TEST"


def test_marker_promotes_unknown_event():
    policy = _enabled_policy()
    payload = {"event_type": "discord.custom.thing", "metadata": {"real_delivery": True}}
    decision = classify_real_delivery(payload, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_ALLOWED


def test_top_level_marker_promotes_unknown_event():
    policy = _enabled_policy()
    payload = {"event_type": "discord.custom.thing", "real_delivery": True}
    decision = classify_real_delivery(payload, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_ALLOWED


def test_denylist_wins_over_marker():
    policy = _enabled_policy()
    payload = {
        "event_type": "github.sandbox_pr.created",
        "metadata": {"real_delivery": True},
    }
    decision = classify_real_delivery(payload, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_EVENT_DENIED


def test_production_executed_true_blocks():
    policy = _enabled_policy()
    payload = {
        "event_type": "discord.real_test_sent",
        "metadata": {"production_executed": True},
    }
    decision = classify_real_delivery(payload, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_PRODUCTION_EXECUTED


def test_wrong_channel_blocks():
    policy = _enabled_policy()
    payload = {"event_type": "discord.real_test_sent", "target_channel": "OTHER"}
    decision = classify_real_delivery(payload, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_WRONG_CHANNEL


def test_missing_marker_when_marker_disabled():
    policy = _enabled_policy(allow_marker=False)
    payload = {"event_type": "discord.custom.thing"}
    decision = classify_real_delivery(payload, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_EVENT_NOT_ALLOWED


def test_missing_marker_when_marker_enabled_but_no_marker():
    policy = _enabled_policy()
    payload = {"event_type": "discord.custom.thing"}
    decision = classify_real_delivery(payload, policy)
    assert decision.decision == DELIVERY_DECISION_REAL_BLOCKED
    assert decision.reason == REASON_MISSING_MARKER


def test_decision_dict_carries_no_token():
    policy = _enabled_policy()
    payload = {
        "event_type": "discord.real_test_sent",
        # Smuggle a fake token to ensure the decision dict never echoes it.
        "secret": "ghp_should_not_leak",  # noqa: S105 - test fixture
        "metadata": {"token": "DISCORD_FAKE_TOKEN_VALUE"},
    }
    decision = classify_real_delivery(payload, policy)
    safe = decision.to_safe_dict()
    text = repr(safe)
    assert "ghp_" not in text
    assert "FAKE_TOKEN" not in text


def test_load_policy_from_env_defaults():
    env = {
        "DISCORD_BOT_TOKEN": "x",
        "DISCORD_TEST_CHANNEL_ID": "C-T",
        "RUN_REAL_DISCORD_TEST": "true",
    }
    policy = load_policy_from_env(env)
    assert policy.real_mode_enabled is True
    assert "discord.real_test_sent" in policy.allowlist
    assert "workflow.*" in policy.denylist
    assert policy.allow_marker is True
    assert policy.test_channel_id == "C-T"


def test_load_policy_from_env_marker_off():
    env = {
        "DISCORD_BOT_TOKEN": "x",
        "DISCORD_TEST_CHANNEL_ID": "C-T",
        "RUN_REAL_DISCORD_TEST": "true",
        "REAL_DISCORD_ALLOW_MARKER": "false",
    }
    policy = load_policy_from_env(env)
    assert policy.allow_marker is False


def test_load_policy_from_env_custom_lists():
    env = {
        "DISCORD_BOT_TOKEN": "x",
        "DISCORD_TEST_CHANNEL_ID": "C-T",
        "RUN_REAL_DISCORD_TEST": "true",
        "REAL_DISCORD_ALLOWLIST": "discord.custom.a, discord.custom.b",
        "REAL_DISCORD_DENYLIST": "secret.*, internal.*",
    }
    policy = load_policy_from_env(env)
    assert policy.allowlist == ["discord.custom.a", "discord.custom.b"]
    assert policy.denylist == ["secret.*", "internal.*"]


def test_safe_dict_does_not_expose_token():
    policy = load_policy_from_env(
        {
            "DISCORD_BOT_TOKEN": "ghp_fakefakefake",
            "DISCORD_TEST_CHANNEL_ID": "C-T",
            "RUN_REAL_DISCORD_TEST": "true",
        }
    )
    safe = policy.to_safe_dict()
    assert "DISCORD_BOT_TOKEN" not in repr(safe)
    assert "ghp_" not in repr(safe)
    assert safe["test_channel_id_configured"] is True
