"""Stage 50 -- Admin Console v0 read-only aggregate operations API.

Six read-only GET endpoints that aggregate the scattered ``/operations/*`` data
into the shapes the Admin Console v0 frontend needs. Strictly read-only: no DB
write, no Redis write, no agent / build / delivery / approval trigger, no side
effects. Responses carry statuses / ids / counts / summaries only -- never
secrets or chain-of-thought.

Each external data source is wrapped defensively: a failing store degrades to a
safe default so the console never crashes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from shared.sdk.delivery_package import DeliveryPackageStore
from shared.sdk.mini_delivery_pilot import MiniDeliveryPilotStore
from shared.sdk.project_planning import ProjectPlanningStore

router = APIRouter(prefix="/operations/admin-console", tags=["admin-console"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_store() -> ProjectPlanningStore:
    return ProjectPlanningStore()


def _pilot_store() -> MiniDeliveryPilotStore:
    return MiniDeliveryPilotStore()


def _package_store() -> DeliveryPackageStore:
    return DeliveryPackageStore()


async def _safe(coro, default):
    try:
        return await coro
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Read-only safety / regression helpers (reuse operations module, defensively).
# ---------------------------------------------------------------------------
async def _safety_summary() -> dict:
    """Compact, read-only safety snapshot for the console."""
    summary: dict = {
        "result": "unknown",
        "production_executed_true_count": None,
        "delivery_package_operator_actions_enabled": False,
        "delivery_package_auto_accept_enabled": False,
        "delivery_package_real_llm_enabled": False,
        "delivery_package_github_write_enabled": False,
        "delivery_package_pr_creation_enabled": False,
        "delivery_package_deploy_enabled": False,
        "delivery_package_external_delivery_enabled": False,
        "latest_human_acceptance_status": None,
        "latest_delivery_readiness_status": None,
        "latest_delivery_package_status": None,
        "latest_acceptance_gate_decision": None,
        "delivery_package_ready_for_admin_console": False,
        "admin_console_enabled": True,
        "admin_console_read_only": True,
        "admin_console_operator_actions_enabled": False,
        "admin_console_write_api_enabled": False,
        "admin_console_secret_redaction_enabled": True,
    }
    try:
        import operations

        prod = await operations._production_safety()
        summary["result"] = prod.get("result", "unknown")
        summary["production_executed_true_count"] = prod.get(
            "workflow_states_production_executed_true", 0
        )
        dp = await operations._delivery_package_safety_summary()
        for k in (
            "delivery_package_operator_actions_enabled",
            "delivery_package_auto_accept_enabled",
            "delivery_package_real_llm_enabled",
            "delivery_package_github_write_enabled",
            "delivery_package_pr_creation_enabled",
            "delivery_package_deploy_enabled",
            "delivery_package_external_delivery_enabled",
            "latest_human_acceptance_status",
            "latest_delivery_readiness_status",
            "latest_delivery_package_status",
            "latest_acceptance_gate_decision",
            "delivery_package_ready_for_admin_console",
        ):
            if k in dp:
                summary[k] = dp[k]
        summary.update(admin_console_safety_flags())
    except Exception:
        pass
    return summary


async def _regression_summary() -> dict:
    try:
        import operations

        return operations._verification_environment_summary()
    except Exception:
        return {
            "verification_environment_ready": False,
            "latest_full_regression_status": "unknown",
            "verification_known_gaps": [],
        }


async def _backup_gaps() -> dict:
    try:
        import operations

        return operations._backup_safety_summary()
    except Exception:
        return {}


async def _incident_counts() -> dict:
    try:
        import operations

        return await operations._incidents_summary()
    except Exception:
        return {"open": 0, "acknowledged": 0, "resolved": 0, "unresolved": 0}


async def _llm_summary() -> dict:
    try:
        import operations

        return await operations._llm_summary()
    except Exception:
        return {}


def admin_console_safety_flags() -> dict:
    """The Admin Console v0 read-only posture (booleans only)."""
    return {
        "admin_console_enabled": True,
        "admin_console_read_only": True,
        "admin_console_operator_actions_enabled": False,
        "admin_console_write_api_enabled": False,
        "admin_console_secret_redaction_enabled": True,
    }


# ---------------------------------------------------------------------------
# Per-project rollup.
# ---------------------------------------------------------------------------
async def _project_rollup(project: dict) -> dict:
    pid = project["id"]
    pilot = await _safe(_pilot_store().get_latest_pilot(pid), None)
    package = await _safe(_package_store().get_latest_package(pid), None)
    readiness = None
    if package:
        readiness = await _safe(_package_store().get_readiness_snapshot(package["id"]), None)
    return {
        "project_id": pid,
        "title": project.get("title"),
        "status": project.get("status"),
        "project_type": project.get("project_type"),
        "risk_level": project.get("risk_level"),
        "autonomy_level": project.get("autonomy_level"),
        "latest_pilot_status": (pilot or {}).get("status"),
        "latest_delivery_package_status": (package or {}).get("status"),
        "human_acceptance_status": (package or {}).get("human_acceptance_status"),
        "readiness_status": (readiness or {}).get("readiness_status"),
    }


# ---------------------------------------------------------------------------
# Endpoints.
# ---------------------------------------------------------------------------
@router.get("/overview")
async def overview() -> dict:
    projects = await _safe(_project_store().list_projects(limit=200), [])
    packages = await _safe(_package_store().list_delivery_packages(limit=200), [])
    latest_pilot = await _safe(_pilot_store().get_latest_pilot(), None)
    latest_package = await _safe(_package_store().get_latest_package(), None)
    latest_gate = None
    if latest_package:
        latest_gate = await _safe(_package_store().get_acceptance_gate(latest_package["id"]), None)
    safety = await _safety_summary()
    regression = await _regression_summary()
    backup = await _backup_gaps()
    incidents = await _incident_counts()
    llm = await _llm_summary()
    active_projects = [p for p in projects if p.get("status") not in ("completed", "archived")]
    ready_packages = [p for p in packages if p.get("status") == "ready_for_review"]
    return {
        "generated_at": _utcnow_iso(),
        "active_projects_count": len(active_projects),
        "projects_count": len(projects),
        "delivery_packages_count": len(packages),
        "ready_for_review_packages_count": len(ready_packages),
        "latest_mini_delivery_pilot_status": (latest_pilot or {}).get("status"),
        "latest_delivery_package_status": (latest_package or {}).get("status"),
        "latest_acceptance_gate_decision": (latest_gate or {}).get("decision"),
        "latest_acceptance_gate_status": (latest_gate or {}).get("status"),
        "latest_human_acceptance_status": (latest_package or {}).get("human_acceptance_status"),
        "safety_result": safety.get("result"),
        "production_executed_true_count": safety.get("production_executed_true_count"),
        "delivery_package_ready_for_admin_console": safety.get(
            "delivery_package_ready_for_admin_console"
        ),
        "latest_full_regression_status": regression.get("latest_full_regression_status"),
        "backup_readiness_gaps": backup.get("backup_gaps", []),
        "backup_production_ready": backup.get("backup_production_ready", False),
        "incidents_summary": incidents,
        "llm_summary": {
            "total_interactions": llm.get("total_interactions", 0),
            "total_proposals": llm.get("total_proposals", 0),
            "estimated_cost": llm.get("estimated_cost", 0.0),
        },
        "admin_console": admin_console_safety_flags(),
    }


@router.get("/projects")
async def projects() -> dict:
    rows = await _safe(_project_store().list_projects(limit=200), [])
    rollups = []
    for p in rows:
        rollups.append(await _project_rollup(p))
    return {"count": len(rollups), "projects": rollups}


@router.get("/projects/{project_id}")
async def project_detail(project_id: str) -> dict:
    project = await _safe(_project_store().get_project(project_id), None)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    rollup = await _project_rollup(project)
    pilot = await _safe(_pilot_store().get_latest_pilot(project_id), None)
    package = await _safe(_package_store().get_latest_package(project_id), None)
    return {
        "project": project,
        "rollup": rollup,
        "latest_pilot": pilot,
        "latest_delivery_package": package,
    }


@router.get("/latest-delivery-state")
async def latest_delivery_state() -> dict:
    pilot = await _safe(_pilot_store().get_latest_pilot(), None)
    package = await _safe(_package_store().get_latest_package(), None)
    gate = None
    readiness = None
    if package:
        gate = await _safe(_package_store().get_acceptance_gate(package["id"]), None)
        readiness = await _safe(_package_store().get_readiness_snapshot(package["id"]), None)
    return {
        "latest_pilot": pilot,
        "latest_delivery_package": package,
        "acceptance_gate": gate,
        "readiness_snapshot": readiness,
        "human_acceptance_status": (package or {}).get("human_acceptance_status"),
        "production_executed": False,
    }


@router.get("/safety-summary")
async def safety_summary() -> dict:
    return await _safety_summary()


@router.get("/regression-summary")
async def regression_summary() -> dict:
    return await _regression_summary()


__all__ = ["router", "admin_console_safety_flags"]
