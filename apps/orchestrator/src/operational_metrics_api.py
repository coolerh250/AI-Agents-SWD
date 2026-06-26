"""Step 58 (Stage 60A) -- read-only Admin Console v2 operational metrics API.

GET-only visibility over a live, redacted operational metrics aggregation. There is
NO generate / refresh / sync / deploy / PR / external-send endpoint, NO mutation, NO
arbitrary path input, NO cluster call. Unavailable / stale sources are explicit;
missing data is never reported as clean. Responses never carry a secret / token /
kubeconfig / chain-of-thought. Metrics are visibility only -- not production readiness.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from shared.sdk.operations_metrics import build_snapshot

router = APIRouter(prefix="/operations/metrics", tags=["operational-metrics"])

_CACHE: dict[str, Any] = {"at": 0.0, "snapshot": None}
_TTL_SECONDS = 10.0


async def _snapshot() -> dict[str, Any]:
    now = time.time()
    if _CACHE["snapshot"] is None or (now - _CACHE["at"]) > _TTL_SECONDS:
        _CACHE["snapshot"] = await build_snapshot()
        _CACHE["at"] = now
    return _CACHE["snapshot"]


async def _domain(name: str) -> dict[str, Any]:
    snap = await _snapshot()
    return {
        "domain": name,
        "production_ready": False,
        **(snap["domains"].get(name) or {"available": False, "reason": "unknown_domain"}),
    }


@router.get("/overview")
async def metrics_overview() -> dict:
    snap = await _snapshot()
    dom = snap["domains"]
    return {
        "production_ready": False,
        "status": snap["status"],
        "generated_at": snap["generated_at"],
        "domain_availability": {k: bool(v.get("available", True)) for k, v in dom.items()},
        "blockers": snap["blockers"],
        "project_count_total": (dom.get("delivery") or {}).get("project_count_total"),
        "work_item_count_total": (dom.get("work_items") or {}).get("work_item_count_total"),
        "dispatch_count_total": (dom.get("dispatch") or {}).get("dispatch_count_total"),
        "production_executed_true_count": (dom.get("safety") or {}).get(
            "production_executed_true_count"
        ),
        "limitations": snap["limitations"],
    }


@router.get("/delivery")
async def metrics_delivery() -> dict:
    return await _domain("delivery")


@router.get("/work-items")
async def metrics_work_items() -> dict:
    return await _domain("work_items")


@router.get("/dispatch")
async def metrics_dispatch() -> dict:
    return await _domain("dispatch")


@router.get("/agents")
async def metrics_agents() -> dict:
    return await _domain("agents")


@router.get("/workflows")
async def metrics_workflows() -> dict:
    return await _domain("workflows")


@router.get("/runtime")
async def metrics_runtime() -> dict:
    return await _domain("runtime")


@router.get("/gitops")
async def metrics_gitops() -> dict:
    return await _domain("gitops")


@router.get("/security")
async def metrics_security() -> dict:
    return await _domain("security")


@router.get("/approval")
async def metrics_approval() -> dict:
    return await _domain("approval")


@router.get("/audit")
async def metrics_audit() -> dict:
    return await _domain("audit")


@router.get("/safety")
async def metrics_safety() -> dict:
    return await _domain("safety")


@router.get("/freshness")
async def metrics_freshness() -> dict:
    snap = await _snapshot()
    return {"production_ready": False, "freshness": snap["freshness"]}


@router.get("/snapshot")
async def metrics_snapshot() -> dict:
    return await _snapshot()


__all__ = ["router"]
