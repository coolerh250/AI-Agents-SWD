"""Step 61 -- backup / restore / DR policy."""

from __future__ import annotations

from shared.sdk.backup_restore_dr import policy


def test_dangerous_toggles_false() -> None:
    p = policy.load_policy()
    assert p.get("enabled") is True
    for key in (
        "productionReady",
        "allowProductionRestore",
        "allowProductionFailover",
        "allowProductionBackupMutation",
        "allowExternalBackupUpload",
        "allowCloudProviderWrite",
        "allowArgoCDProductionSync",
        "allowKubernetesProductionMutation",
        "allowUnreviewedCleanup",
        "allowCleanupExecution",
        "allowRestoreExecution",
        "allowKindTeardown",
        "allowArgoCDTeardown",
    ):
        assert p.get(key, False) is False, key


def test_required_guards_true() -> None:
    p = policy.load_policy()
    assert p.get("requireInventoryBeforeCleanup") is True
    assert p.get("requireRestoreValidation") is True
    assert p.get("requireHumanApprovalForProductionRestore") is True


def test_environment_validation() -> None:
    for env in ("production", "prod"):
        _, blocked = policy.validate_environment(env)
        assert blocked == "production_environment_forbidden"
    for env in ("local", "dev", "test", "nonprod"):
        _, blocked = policy.validate_environment(env)
        assert blocked is None
