"""Step 58 -- operational metrics aggregator.

Builds a redacted operational metrics snapshot from read-only sources. Unavailable /
stale sources are explicit; missing data is never reported as clean; nothing here
mutates, syncs, deploys, or calls external services. productionReady is always false.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.sdk.operations_metrics import collectors
from shared.sdk.operations_metrics.redaction import redact

ROOT = Path(__file__).resolve().parents[3]


async def build_snapshot(
    root: Path | None = None, database_url: str | None = None
) -> dict[str, Any]:
    base = root or ROOT
    domains: dict[str, Any] = {}
    db_available = True
    try:
        conn = await collectors.db_connect(database_url)
    except Exception:  # noqa: BLE001 -- DB unavailable degrades, never fakes
        conn = None
        db_available = False

    if conn is not None:
        try:
            domains["delivery"] = await collectors.collect_delivery(conn)
            domains["work_items"] = await collectors.collect_work_items(conn)
            domains["dispatch"] = await collectors.collect_dispatch(conn)
            domains["agents"] = await collectors.collect_agents(conn)
            domains["workflows"] = await collectors.collect_workflows(conn)
            domains["approval"] = await collectors.collect_approval(conn)
            domains["audit"] = await collectors.collect_audit(conn)
            domains["safety"] = await collectors.collect_safety(conn, base)
        finally:
            await conn.close()
    else:
        for d in (
            "delivery",
            "work_items",
            "dispatch",
            "agents",
            "workflows",
            "approval",
            "audit",
            "safety",
        ):
            domains[d] = {"available": False, "reason": "database_unavailable"}

    domains["runtime"] = collectors.collect_runtime(base)
    domains["gitops"] = collectors.collect_gitops(base)
    domains["security"] = collectors.collect_security(base)

    freshness = {
        "runtime": domains["runtime"].get("freshness")
        or domains["runtime"].get("nonprod_runtime_report_freshness"),
        "gitops": domains["gitops"].get("freshness")
        or domains["gitops"].get("argocd_report_freshness"),
        "database": {"available": db_available},
    }
    limitations = [
        "operational metrics are visibility only; not production readiness / SLA / SLO",
        "runtime reports are not committed; absent reports are shown stale/unavailable",
    ]
    blockers = [name for name, d in domains.items() if d.get("available") is False]

    snapshot = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_version": "1",
        "status": "modeled_not_production_ready",
        "production_ready": False,
        "domains": domains,
        "freshness": freshness,
        "limitations": limitations,
        "blockers": blockers,
    }
    return redact(snapshot)
