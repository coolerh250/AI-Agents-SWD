"""Stage 45 -- ProjectPlanningStore URL behavior + full-graph persistence.

The asyncpg integration runs on the test server; here we cover the dsn
behavior and a full plan->persist round trip against the in-memory fake.
"""

from __future__ import annotations

import pytest

from project_planning_fakes import FakeProjectStore

from shared.sdk.project_planning import PlannerInput, ProjectPlanningStore, plan_project


def test_store_uses_default_url() -> None:
    assert ProjectPlanningStore().database_url.startswith("postgresql://")


def test_store_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@y:5432/env-db")
    assert "env-db" in ProjectPlanningStore().database_url


async def test_plan_persists_full_graph() -> None:
    store = FakeProjectStore()
    out = await plan_project(
        PlannerInput(request_text="Create a FastAPI Todo Service with CRUD and SQLite"),
        store,
        emit_events=False,
    )
    pid = out.project_id
    assert store.projects[pid]["status"] == "planned"
    assert store.briefs[pid]["scope"]
    assert len(store.work_items[pid]) >= 8
    assert len(store.dependencies[pid]) >= 5
    assert len(store.acceptance[pid]) >= 8
    assert len(store.milestones[pid]) >= 7
    assert store.snapshots[pid][-1]["validation_status"] == "valid"
    assert out.requires_clarification is False
    assert out.production_executed is False


async def test_plan_clarification_path() -> None:
    store = FakeProjectStore()
    out = await plan_project(PlannerInput(request_text="todo"), store, emit_events=False)
    assert out.requires_clarification is True
    assert store.projects[out.project_id]["status"] == "draft"
    assert store.work_items.get(out.project_id) is None


async def test_ready_work_items_and_progress() -> None:
    store = FakeProjectStore()
    out = await plan_project(
        PlannerInput(request_text="Build a FastAPI Todo API with SQLite"),
        store,
        emit_events=False,
    )
    progress = await store.compute_project_progress(out.project_id)
    assert progress["work_items_total"] >= 8
    assert progress["work_items_completed"] == 0
