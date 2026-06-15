# FastAPI Todo Mini Delivery Pilot (Stage 48)

## Request

```
Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples.
```

## Generated project

The pilot reuses the Stage 47 controlled workspace operator, which generates
the deterministic FastAPI Todo project (≥8 files: `app/main.py` CRUD over
SQLite, `schemas.py`, `crud.py`, `database.py`, `models.py`, `README.md`,
`tests/test_todos.py`). See
[fastapi-todo-workspace-template.md](fastapi-todo-workspace-template.md).

## Tests

`pytest` runs in the controlled workspace (create / list / get / update /
delete + 404 + 422); `compileall` always runs; `ruff` runs when available.

## Acceptance mapping

| Criterion | Evidence |
| --------- | -------- |
| AC-001..005 (CRUD) | `test_run` — pytest passed |
| AC-006 (SQLite persistence) | `test_run` (+ generated `app/database.py`) |
| AC-007 (pytest suite passes) | `test_run` — pytest passed |
| AC-008 (README setup/run/test/API) | `generated_file` — `README.md` present |
| AC-009 (no production deployment) | `static_check` — safety evidence |
| AC-010 (no secret required) | `static_check` — safety evidence |

Target for the FastAPI Todo template: ≥8 satisfied, 0 failed; criteria with
genuinely unavailable evidence are `pending` (never auto-satisfied,
never auto-waived).

## Known limitations

* No auth; local SQLite only; no production deployment; no real PR this stage.

## How to inspect the result

```bash
# run a controlled pilot
curl -X POST localhost:8000/operations/mini-delivery-pilots/run \
  -H 'Content-Type: application/json' \
  -d '{"request_text":"Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples."}'

# then, with the returned pilot_id:
curl localhost:8000/operations/mini-delivery-pilots/<pilot_id>/steps
curl localhost:8000/operations/mini-delivery-pilots/<pilot_id>/acceptance-evaluations
curl localhost:8000/operations/mini-delivery-pilots/<pilot_id>/qa-report
curl localhost:8000/operations/mini-delivery-pilots/<pilot_id>/safety-report
curl localhost:8000/operations/mini-delivery-pilots/<pilot_id>/report
curl localhost:8000/operations/mini-delivery-pilots/<pilot_id>/timeline
```
