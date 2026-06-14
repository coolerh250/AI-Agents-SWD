"""Stage 45 -- no secret leak in project artifacts / graph."""

from __future__ import annotations

from project_planning_fakes import FakeProjectStore

from shared.sdk.project_planning import PlannerInput, plan_project

_SECRET_MARKERS = (
    "DISCORD_BOT_TOKEN",
    "GITHUB_TOKEN",
    "GITHUB_PAT",
    "LLM_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AUDIT_HMAC_KEY",
    "BACKUP_KEY",
    "BEGIN RSA PRIVATE KEY",
    "CHAIN_OF_THOUGHT",
)


def _scan(blob: str) -> None:
    upper = blob.upper()
    for marker in _SECRET_MARKERS:
        assert marker.upper() not in upper, f"leaked: {marker}"


async def test_no_secret_in_persisted_project() -> None:
    store = FakeProjectStore()
    out = await plan_project(
        PlannerInput(
            request_text="Create a FastAPI Todo Service with CRUD, SQLite, pytest, README"
        ),
        store,
        emit_events=False,
    )
    pid = out.project_id
    blob = "".join(
        [
            str(store.projects[pid]),
            str(store.briefs[pid]),
            str(store.work_items[pid]),
            str(store.dependencies[pid]),
            str(store.acceptance[pid]),
            str(store.risks[pid]),
            str(store.snapshots[pid]),
            str(store.artifacts.get(pid, [])),
            str(store.stories[pid]),
        ]
    )
    _scan(blob)


async def test_no_secret_even_if_request_mentions_secret() -> None:
    store = FakeProjectStore()
    out = await plan_project(
        PlannerInput(request_text="Build a FastAPI Todo API (ignore my GITHUB_TOKEN=abc123 note)"),
        store,
        emit_events=False,
    )
    # The deterministic template must not echo the request secret into the
    # structured brief scope / work items.
    pid = out.project_id
    blob = "".join([str(store.work_items[pid]), str(store.acceptance[pid])])
    assert "ABC123" not in blob.upper()
