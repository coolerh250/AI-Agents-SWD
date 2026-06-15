"""Stage 47 -- deterministic FastAPI Todo project generator.

Pure: given a project brief / design-review summary / work items, returns a
mapping of ``relative_path -> file_content``. No LLM, no network, no secrets,
no production deploy config. The generated project uses only the standard
library ``sqlite3`` for persistence plus FastAPI for the API, so the only test
dependencies are ``fastapi``, ``httpx`` (TestClient), and ``pytest``.
"""

from __future__ import annotations

EXECUTION_TYPE = "fastapi_todo_generation"

_PYPROJECT = """\
[project]
name = "fastapi-todo-service"
version = "0.1.0"
description = "Controlled-generation FastAPI Todo Service (CRUD + SQLite)."
requires-python = ">=3.10"
dependencies = [
    "fastapi",
    "uvicorn",
    "pydantic>=2",
]

[project.optional-dependencies]
test = [
    "pytest",
    "httpx",
]

[tool.ruff]
line-length = 100

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["app"]
"""

_REQUIREMENTS = """\
fastapi
uvicorn
pydantic>=2
# test-only
pytest
httpx
"""

_GITIGNORE = """\
__pycache__/
*.pyc
*.db
.pytest_cache/
.ruff_cache/
"""

_APP_INIT = '"""FastAPI Todo Service (controlled generation)."""\n'

_DATABASE = '''\
"""SQLite persistence for the Todo service (standard-library sqlite3).

The database path is read lazily from ``TODO_DB_PATH`` so tests can point it
at a temporary file before the app starts. No external database, no secrets.
"""

from __future__ import annotations

import os
import sqlite3

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _db_path() -> str:
    return os.environ.get("TODO_DB_PATH", "todos.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()
'''

_MODELS = '''\
"""Domain model description for the Todo resource.

Persistence uses the standard-library sqlite3 (see database.py); this module
documents the row shape and the SQL column contract.
"""

from __future__ import annotations

from dataclasses import dataclass

TODO_COLUMNS = ("id", "title", "description", "completed", "created_at", "updated_at")


@dataclass
class Todo:
    id: int
    title: str
    description: str
    completed: bool
    created_at: str
    updated_at: str


def row_to_todo(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "completed": bool(row["completed"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
'''

_SCHEMAS = '''\
"""Pydantic request/response schemas for the Todo API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    completed: bool = False


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None


class TodoOut(BaseModel):
    id: int
    title: str
    description: str
    completed: bool
    created_at: str
    updated_at: str
'''

_CRUD = '''\
"""CRUD operations backed by sqlite3."""

from __future__ import annotations

from datetime import datetime, timezone

from app.database import get_conn
from app.models import row_to_todo


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_todo(title: str, description: str = "", completed: bool = False) -> dict:
    now = _now()
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO todos (title, description, completed, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, description, 1 if completed else 0, now, now),
        )
        conn.commit()
        todo_id = cur.lastrowid
    finally:
        conn.close()
    return get_todo(todo_id)


def list_todos() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM todos ORDER BY id").fetchall()
    finally:
        conn.close()
    return [row_to_todo(r) for r in rows]


def get_todo(todo_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    finally:
        conn.close()
    return row_to_todo(row) if row else None


def update_todo(
    todo_id: int,
    title: str | None = None,
    description: str | None = None,
    completed: bool | None = None,
) -> dict | None:
    existing = get_todo(todo_id)
    if existing is None:
        return None
    new_title = existing["title"] if title is None else title
    new_desc = existing["description"] if description is None else description
    new_done = existing["completed"] if completed is None else completed
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE todos SET title = ?, description = ?, completed = ?, updated_at = ? "
            "WHERE id = ?",
            (new_title, new_desc, 1 if new_done else 0, _now(), todo_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_todo(todo_id)


def delete_todo(todo_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
    finally:
        conn.close()
    return cur.rowcount > 0
'''

_MAIN = '''\
"""FastAPI Todo Service -- CRUD endpoints over SQLite."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException

from app import crud
from app.database import init_db
from app.schemas import TodoCreate, TodoOut, TodoUpdate


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="FastAPI Todo Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/todos", response_model=TodoOut, status_code=201)
def create_todo(payload: TodoCreate) -> dict:
    return crud.create_todo(payload.title, payload.description, payload.completed)


@app.get("/todos", response_model=list[TodoOut])
def list_todos() -> list[dict]:
    return crud.list_todos()


@app.get("/todos/{todo_id}", response_model=TodoOut)
def get_todo(todo_id: int) -> dict:
    todo = crud.get_todo(todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="todo not found")
    return todo


@app.put("/todos/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: int, payload: TodoUpdate) -> dict:
    todo = crud.update_todo(
        todo_id, payload.title, payload.description, payload.completed
    )
    if todo is None:
        raise HTTPException(status_code=404, detail="todo not found")
    return todo


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int) -> None:
    if not crud.delete_todo(todo_id):
        raise HTTPException(status_code=404, detail="todo not found")
'''

_TEST_TODOS = '''\
"""Tests for the FastAPI Todo Service (isolated temp SQLite DB)."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["TODO_DB_PATH"] = path
    # import after the env is set so the app uses the temp DB.
    from app.main import app

    with TestClient(app) as c:
        yield c
    if os.path.exists(path):
        os.remove(path)


def test_create_todo(client):
    resp = client.post("/todos", json={"title": "first", "description": "d"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] >= 1
    assert body["title"] == "first"
    assert body["completed"] is False


def test_list_todos(client):
    client.post("/todos", json={"title": "a"})
    client.post("/todos", json={"title": "b"})
    resp = client.get("/todos")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_todo(client):
    created = client.post("/todos", json={"title": "x"}).json()
    resp = client.get(f"/todos/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "x"


def test_update_todo(client):
    created = client.post("/todos", json={"title": "x"}).json()
    resp = client.put(
        f"/todos/{created['id']}", json={"title": "y", "completed": True}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "y"
    assert resp.json()["completed"] is True


def test_delete_todo(client):
    created = client.post("/todos", json={"title": "x"}).json()
    resp = client.delete(f"/todos/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/todos/{created['id']}").status_code == 404


def test_get_not_found(client):
    assert client.get("/todos/999999").status_code == 404


def test_create_validation_error(client):
    resp = client.post("/todos", json={"title": ""})
    assert resp.status_code == 422
'''

_README = """\
# FastAPI Todo Service

A small FastAPI Todo service with CRUD endpoints and SQLite persistence.

> Generated by the controlled Real Repo Workspace Operator (Stage 47).
> Deterministic template -- no LLM, no secrets, no production deployment.

## Overview

| Resource | Fields |
| -------- | ------ |
| Todo | id, title, description, completed, created_at, updated_at |

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .[test]
```

## Run the server

```bash
uvicorn app.main:app --reload
```

The SQLite database path defaults to `todos.db` and can be overridden with the
`TODO_DB_PATH` environment variable.

## Run the tests

```bash
python -m pytest
```

## API examples

```bash
# create
curl -X POST localhost:8000/todos -H 'Content-Type: application/json' \\
  -d '{"title": "buy milk", "description": "2 litres"}'

# list
curl localhost:8000/todos

# get one
curl localhost:8000/todos/1

# update
curl -X PUT localhost:8000/todos/1 -H 'Content-Type: application/json' \\
  -d '{"completed": true}'

# delete
curl -X DELETE localhost:8000/todos/1
```

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | /todos | Create a todo |
| GET | /todos | List todos |
| GET | /todos/{id} | Get one todo |
| PUT | /todos/{id} | Update a todo |
| DELETE | /todos/{id} | Delete a todo |

## Known limitations

- No authentication / authorization (out of scope).
- Local SQLite only; not multi-user / not horizontally scalable.
- No production deployment configuration (no Docker / Kubernetes).
"""


def build_fastapi_todo_files(
    *,
    brief: dict | None = None,
    design_review_summary: dict | None = None,
    work_items: list[dict] | None = None,
    acceptance_criteria: list[dict] | None = None,
) -> dict[str, str]:
    """Return ``{relative_path: content}`` for a complete FastAPI Todo project.

    Inputs are accepted for traceability but the output is deterministic; the
    template already encodes the design-review API/data-model/QA/delivery
    recommendations (POST/GET/PUT/DELETE /todos, SQLite, pytest, README).
    """
    return {
        "pyproject.toml": _PYPROJECT,
        "requirements.txt": _REQUIREMENTS,
        ".gitignore": _GITIGNORE,
        "README.md": _README,
        "app/__init__.py": _APP_INIT,
        "app/main.py": _MAIN,
        "app/database.py": _DATABASE,
        "app/models.py": _MODELS,
        "app/schemas.py": _SCHEMAS,
        "app/crud.py": _CRUD,
        "tests/__init__.py": "",
        "tests/test_todos.py": _TEST_TODOS,
    }


def file_type_for(relative_path: str) -> str:
    """Classify a generated file for the workspace_files.file_type column."""
    rp = relative_path.replace("\\", "/")
    if rp.startswith("tests/") or rp.endswith("_test.py") or "test_" in rp.rsplit("/", 1)[-1]:
        return "test"
    if rp.endswith(".md"):
        return "documentation"
    if rp.endswith((".toml", ".cfg", ".ini", ".txt", ".gitignore")) or rp.endswith(".gitignore"):
        return "config"
    if rp.endswith(".py"):
        return "source"
    return "generated"


__all__ = ["build_fastapi_todo_files", "file_type_for", "EXECUTION_TYPE"]
