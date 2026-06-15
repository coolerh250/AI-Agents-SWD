"""Stage 50 -- shared wiring for admin console aggregate API tests."""

from __future__ import annotations


async def wire_admin_console(tmp_path, monkeypatch):
    """Build a completed delivery package and point the admin console API + the
    operations safety/regression helpers at in-memory fakes."""
    import admin_console_api
    import operations
    from delivery_package_fakes import build_fake_package

    result, stores = await build_fake_package(tmp_path, monkeypatch)

    monkeypatch.setattr(admin_console_api, "_project_store", lambda: stores["project"])
    monkeypatch.setattr(admin_console_api, "_pilot_store", lambda: stores["pilot"])
    monkeypatch.setattr(admin_console_api, "_package_store", lambda: stores["package"])

    async def _prod_safety():
        return {"result": "safe", "workflow_states_production_executed_true": 0}

    async def _dp_safety():
        return {
            "delivery_package_operator_actions_enabled": False,
            "delivery_package_auto_accept_enabled": False,
            "delivery_package_real_llm_enabled": False,
            "delivery_package_github_write_enabled": False,
            "delivery_package_pr_creation_enabled": False,
            "delivery_package_deploy_enabled": False,
            "delivery_package_external_delivery_enabled": False,
            "latest_human_acceptance_status": "pending",
            "latest_delivery_readiness_status": "ready_for_operator_review",
            "latest_delivery_package_status": "ready_for_review",
            "latest_acceptance_gate_decision": "ready_for_operator_review",
            "delivery_package_ready_for_admin_console": True,
        }

    def _regression():
        return {
            "verification_environment_ready": True,
            "latest_full_regression_status": "passed_with_documented_gaps",
            "verification_known_gaps": ["backup_readiness"],
        }

    def _backup():
        return {"backup_gaps": ["encryption_no_key"], "backup_production_ready": False}

    async def _incidents():
        return {"open": 0, "acknowledged": 0, "resolved": 0, "unresolved": 0}

    async def _llm():
        return {"total_interactions": 0, "total_proposals": 0, "estimated_cost": 0.0}

    monkeypatch.setattr(operations, "_production_safety", _prod_safety)
    monkeypatch.setattr(operations, "_delivery_package_safety_summary", _dp_safety)
    monkeypatch.setattr(operations, "_verification_environment_summary", _regression)
    monkeypatch.setattr(operations, "_backup_safety_summary", _backup)
    monkeypatch.setattr(operations, "_incidents_summary", _incidents)
    monkeypatch.setattr(operations, "_llm_summary", _llm)

    return result, stores
