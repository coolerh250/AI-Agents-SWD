# FastAPI Todo Workspace Template (Stage 47)

The deterministic project the workspace operator generates for the
`fastapi_todo_service` template.

## Generated project structure

```
fastapi-todo-service/
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   └── crud.py
└── tests/
    ├── __init__.py
    └── test_todos.py
```

## API endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | /todos | Create a todo |
| GET | /todos | List todos |
| GET | /todos/{todo_id} | Get one todo |
| PUT | /todos/{todo_id} | Update a todo |
| DELETE | /todos/{todo_id} | Delete a todo |
| GET | /health | Liveness |

## Data model

`Todo`: `id`, `title`, `description`, `completed`, `created_at`,
`updated_at`. Persistence uses the standard-library `sqlite3` (no SQLAlchemy,
no external DB). The database path is read lazily from `TODO_DB_PATH`
(default `todos.db`) so tests can isolate it in a temp file.

## Tests

`tests/test_todos.py` uses `fastapi.testclient.TestClient` against an isolated
temp SQLite database and covers create / list / get / update / delete, the
404 not-found path, and a 422 validation error.

## README content

The generated `README.md` includes overview, setup, run-the-server,
run-the-tests, API examples, and a known-limitations section (no auth, local
SQLite only, no production deployment).

## How to run locally

```bash
cd <workspace_root>          # printed as workspace_root in the execution result
python -m venv .venv && . .venv/bin/activate
pip install -e .[test]
python -m pytest
uvicorn app.main:app --reload
```

## Known limitations

* No authentication / authorization (out of scope).
* Local SQLite only; not multi-user / not horizontally scalable.
* No production deployment configuration (no Docker / Kubernetes).
