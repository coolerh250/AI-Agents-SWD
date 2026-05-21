RESTRICTED_ACTIONS = frozenset(
    {
        "production.deploy",
        "production.config.change",
        "email.send",
        "contract.action",
        "cost.commitment",
        "security.policy.change",
        "production.data.delete",
        "secret.rotation",
    }
)


class PolicyClient:
    """Evaluates whether an action is allowed or requires human approval."""

    def __init__(self, restricted_actions: frozenset[str] | None = None) -> None:
        self.restricted_actions = restricted_actions or RESTRICTED_ACTIONS

    def evaluate_policy(self, action: dict) -> dict:
        action_type = action.get("type", "")
        restricted = action_type in self.restricted_actions
        return {
            "action_type": action_type,
            "allowed": not restricted,
            "approval_required": restricted,
        }
