"""Step 58 -- operational metrics collectors (read-only).

Each collector returns {"available": bool, "data"/"reason": ...}. DB collectors are
read-only counts; report collectors read allowlisted runtime/committed files; the
safety collector reflects config production-safety posture. No mutation, no sync, no
external call, no arbitrary path.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import asyncpg
import yaml

from shared.sdk.operations_metrics.freshness import load_json_if_fresh

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


async def _counts(conn: asyncpg.Connection, table: str, column: str) -> dict[str, int]:
    rows = await conn.fetch(f"SELECT {column} AS k, count(*) AS n FROM {table} GROUP BY {column}")
    return {str(r["k"]): int(r["n"]) for r in rows}


async def _total(conn: asyncpg.Connection, table: str) -> int:
    return int(await conn.fetchval(f"SELECT count(*) FROM {table}"))


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"available": True, **data}


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


async def collect_delivery(conn: asyncpg.Connection) -> dict[str, Any]:
    try:
        return _ok(
            {
                "project_count_total": await _total(conn, "projects"),
                "project_count_by_status": await _counts(conn, "projects", "registry_status"),
                "project_count_by_environment_scope": await _counts(
                    conn, "projects", "environment_scope"
                ),
                "project_delivery_state_count_by_status": await _counts(
                    conn, "project_delivery_states", "delivery_state"
                ),
                "delivery_package_linkage_count": await _total(conn, "project_delivery_packages"),
                "production_ready": False,
            }
        )
    except (asyncpg.PostgresError, OSError) as e:
        return _unavailable(f"db_error:{type(e).__name__}")


async def collect_work_items(conn: asyncpg.Connection) -> dict[str, Any]:
    try:
        by_state = await _counts(conn, "project_work_items", "lifecycle_state")
        return _ok(
            {
                "work_item_count_total": await _total(conn, "project_work_items"),
                "work_item_count_by_status": by_state,
                "work_item_count_by_type": await _counts(
                    conn, "project_work_items", "delivery_work_type"
                ),
                "work_item_count_by_priority": await _counts(
                    conn, "project_work_items", "priority"
                ),
                "work_item_waiting_approval_count": by_state.get("waiting_approval", 0),
                "work_item_blocked_count": by_state.get("blocked", 0),
                "work_item_completed_count": by_state.get("completed", 0),
                "production_ready": False,
            }
        )
    except (asyncpg.PostgresError, OSError) as e:
        return _unavailable(f"db_error:{type(e).__name__}")


async def collect_dispatch(conn: asyncpg.Connection) -> dict[str, Any]:
    try:
        by_status = await _counts(conn, "work_item_dispatches", "status")
        return _ok(
            {
                "dispatch_count_total": await _total(conn, "work_item_dispatches"),
                "dispatch_count_by_status": by_status,
                "dispatch_count_by_target_agent": await _counts(
                    conn, "work_item_dispatches", "target_agent"
                ),
                "dispatch_failure_count": by_status.get("failed", 0),
                "production_ready": False,
            }
        )
    except (asyncpg.PostgresError, OSError) as e:
        return _unavailable(f"db_error:{type(e).__name__}")


async def collect_agents(conn: asyncpg.Connection) -> dict[str, Any]:
    try:
        by_status = await _counts(conn, "agent_executions", "status")
        total = sum(by_status.values())
        failures = by_status.get("failed", 0) + by_status.get("error", 0)
        success = by_status.get("completed", 0) + by_status.get("succeeded", 0)
        rate = round(success / total, 4) if total else None
        return _ok(
            {
                "agent_execution_count_total": total,
                "agent_execution_count_by_agent": await _counts(
                    conn, "agent_executions", "agent_name"
                ),
                "agent_execution_count_by_status": by_status,
                "agent_execution_failure_count": failures,
                "agent_execution_success_rate": rate,
            }
        )
    except (asyncpg.PostgresError, OSError) as e:
        return _unavailable(f"db_error:{type(e).__name__}")


async def collect_workflows(conn: asyncpg.Connection) -> dict[str, Any]:
    try:
        by_phase = await _counts(conn, "workflow_states", "phase")
        return _ok(
            {
                "workflow_count_total": await _total(conn, "workflow_states"),
                "workflow_count_by_status": by_phase,
                "workflow_waiting_approval_count": by_phase.get("waiting_approval", 0)
                + by_phase.get("approval", 0),
                "workflow_failed_count": by_phase.get("failed", 0),
            }
        )
    except (asyncpg.PostgresError, OSError) as e:
        return _unavailable(f"db_error:{type(e).__name__}")


async def collect_approval(conn: asyncpg.Connection) -> dict[str, Any]:
    try:
        by_status = await _counts(conn, "approval_requests", "status")
        return _ok(
            {
                "approval_count_total": sum(by_status.values()),
                "approval_count_by_status": by_status,
                "approval_waiting_count": by_status.get("pending", 0),
                "approval_rejected_count": by_status.get("rejected", 0),
                "approval_approved_count": by_status.get("approved", 0),
            }
        )
    except (asyncpg.PostgresError, OSError) as e:
        return _unavailable(f"db_error:{type(e).__name__}")


async def collect_audit(conn: asyncpg.Connection) -> dict[str, Any]:
    try:
        total = await _total(conn, "audit_logs")
        recent = int(
            await conn.fetchval(
                "SELECT count(*) FROM audit_logs WHERE created_at > now() - interval '24 hours'"
            )
        )
        return _ok(
            {
                "audit_event_count_total": total,
                "audit_recent_event_count": recent,
                "audit_integrity_status_if_available": "not_collected_here",
            }
        )
    except (asyncpg.PostgresError, OSError) as e:
        return _unavailable(f"db_error:{type(e).__name__}")


def collect_runtime(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    path = base / ".runtime" / "kubernetes" / "nonproduction-runtime-smoke-report.json"
    data, fr = load_json_if_fresh(path)
    if data is None:
        return {"available": False, "reason": fr["reason"], "freshness": fr}
    sections = data.get("sections", {})
    pods = sections.get("podStatus", {})
    return _ok(
        {
            "nonprod_cluster_detected": True,
            "nonprod_namespace": data.get("namespace"),
            "nonprod_pods_ready": pods.get("ready"),
            "nonprod_pods_total": pods.get("runningExpected"),
            "nonprod_service_health_status": sections.get("serviceHealth", {}).get("status"),
            "nonprod_connectivity_status": sections.get("connectivity", {}).get("status"),
            "nonprod_storage_status": sections.get("pvc", {}).get("status"),
            "nonprod_securitycontext_status": sections.get("securityContext", {}).get("status"),
            "nonprod_networkpolicy_status": sections.get("networkPolicy", {}).get("status"),
            "nonprod_runtime_report_freshness": fr,
            "production_ready": False,
        }
    )


def collect_gitops(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    path = base / ".runtime" / "gitops" / "nonproduction-argocd-manual-sync-report.json"
    data, fr = load_json_if_fresh(path)
    if data is None:
        # Fall back to the committed summary (in-image) for a stale-but-present view.
        summ = base / "infra" / "gitops" / "nonproduction-argocd-manual-sync-summary.yaml"
        if summ.is_file():
            s = (yaml.safe_load(summ.read_text(encoding="utf-8")) or {}).get(
                "nonProductionArgocdManualSyncSummary", {}
            )
            return {
                "available": True,
                "source": "committed_summary",
                "freshness": fr,
                "argocd_installed": s.get("argocdInstalled"),
                "argocd_namespace": s.get("argocdNamespace"),
                "argocd_project": s.get("project"),
                "argocd_application": s.get("application"),
                "argocd_last_manual_sync_status": s.get("lastSyncStatus"),
                "argocd_health_status": s.get("lastHealthStatus"),
                "argocd_auto_sync_enabled": s.get("autoSyncEnabled"),
                "argocd_prune_enabled": s.get("pruneEnabled"),
                "argocd_self_heal_enabled": s.get("selfHealEnabled"),
                "production_ready": False,
            }
        return {"available": False, "reason": fr["reason"], "freshness": fr}
    sync = data.get("sync", {})
    return _ok(
        {
            "source": "runtime_report",
            "argocd_installed": True,
            "argocd_namespace": data.get("argocdNamespace"),
            "argocd_project": data.get("project"),
            "argocd_application": data.get("application"),
            "argocd_last_manual_sync_status": sync.get("status"),
            "argocd_health_status": data.get("health", {}).get("status"),
            "argocd_auto_sync_enabled": sync.get("autoSyncEnabled"),
            "argocd_prune_enabled": sync.get("pruneEnabled"),
            "argocd_self_heal_enabled": sync.get("selfHealEnabled"),
            "argocd_report_freshness": fr,
            "production_ready": False,
        }
    )


def collect_security(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    path = base / "infra" / "security" / "security-integrated-summary.yaml"
    if not path.is_file():
        return _unavailable("security_summary_missing")
    s = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    s = s.get("securityIntegratedSummary", s) if isinstance(s, dict) else {}
    return _ok(
        {
            "security_baseline_status": "modeled_not_enforced",
            "security_readiness_status": "modeled_not_production_ready",
            "security_production_ready": False,
            "summary_present": True,
        }
    )


async def collect_safety(conn: asyncpg.Connection, root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    from shared.sdk.argocd_sync import nonprod_argocd_safety_fields
    from shared.sdk.runtime_smoke import nonprod_runtime_safety_fields
    from shared.sdk.work_items.safety import multi_project_safety_fields

    mp = multi_project_safety_fields()
    ac = nonprod_argocd_safety_fields(base)
    rt = nonprod_runtime_safety_fields(base)
    try:
        prod_exec = int(
            await conn.fetchval(
                "SELECT count(*) FROM deployment_records " "WHERE environment='production'"
            )
        )
    except (asyncpg.PostgresError, OSError):
        prod_exec = 0
    return _ok(
        {
            "production_executed_true_count": prod_exec,
            "kubernetes_production_deploy_performed": rt.get(
                "kubernetes_production_deploy_performed", False
            ),
            "argocd_production_sync_performed": ac.get("argocd_production_sync_performed", False),
            "work_item_dispatch_production_action_enabled": mp.get(
                "work_item_dispatch_production_action_enabled", False
            ),
            "multi_project_production_ready": mp.get("multi_project_production_ready", False),
            "nonprod_runtime_smoke_production_ready": rt.get(
                "nonprod_runtime_smoke_production_ready", False
            ),
            "security_step54_production_ready": False,
        }
    )


async def db_connect(database_url: str | None = None) -> asyncpg.Connection:
    return await asyncpg.connect(
        dsn=database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL), timeout=5
    )
