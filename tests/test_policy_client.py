from shared.sdk.policy.client import RESTRICTED_ACTIONS, PolicyClient


def test_restricted_actions_blocked():
    client = PolicyClient()
    for action_type in RESTRICTED_ACTIONS:
        result = client.evaluate_policy({"type": action_type})
        assert result["allowed"] is False
        assert result["approval_required"] is True


def test_non_restricted_action_allowed():
    client = PolicyClient()
    result = client.evaluate_policy({"type": "code.read"})
    assert result["allowed"] is True
    assert result["approval_required"] is False


def test_unknown_action_allowed():
    client = PolicyClient()
    result = client.evaluate_policy({})
    assert result["allowed"] is True
    assert result["approval_required"] is False


def test_expected_restricted_action_set():
    expected = {
        "production.deploy",
        "production.config.change",
        "email.send",
        "contract.action",
        "cost.commitment",
        "security.policy.change",
        "production.data.delete",
        "secret.rotation",
    }
    assert set(RESTRICTED_ACTIONS) == expected
