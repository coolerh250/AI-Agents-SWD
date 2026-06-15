"""Stage 47 -- deterministic FastAPI Todo generator output."""

from __future__ import annotations

from shared.sdk.workspace_operator.fastapi_todo_generator import (
    build_fastapi_todo_files,
    file_type_for,
)

REQUIRED = (
    "pyproject.toml",
    "README.md",
    "app/__init__.py",
    "app/main.py",
    "app/models.py",
    "app/schemas.py",
    "app/database.py",
    "app/crud.py",
    "tests/test_todos.py",
)


def test_required_files_generated() -> None:
    files = build_fastapi_todo_files()
    for path in REQUIRED:
        assert path in files, path
    assert len(files) >= 8


def test_crud_endpoints_present() -> None:
    main = build_fastapi_todo_files()["app/main.py"]
    assert '@app.post("/todos"' in main
    assert '@app.get("/todos"' in main
    assert '@app.get("/todos/{todo_id}"' in main
    assert '@app.put("/todos/{todo_id}"' in main
    assert '@app.delete("/todos/{todo_id}"' in main


def test_sqlite_persistence_present() -> None:
    db = build_fastapi_todo_files()["app/database.py"]
    assert "sqlite3" in db
    assert "CREATE TABLE IF NOT EXISTS todos" in db


def test_todo_fields_present() -> None:
    schemas = build_fastapi_todo_files()["app/schemas.py"]
    for field in ("title", "description", "completed"):
        assert field in schemas
    out = build_fastapi_todo_files()["app/models.py"]
    for field in ("id", "created_at", "updated_at"):
        assert field in out


def test_tests_cover_crud_and_negative() -> None:
    test_file = build_fastapi_todo_files()["tests/test_todos.py"]
    for name in (
        "test_create_todo",
        "test_list_todos",
        "test_get_todo",
        "test_update_todo",
        "test_delete_todo",
        "test_get_not_found",
        "test_create_validation_error",
    ):
        assert name in test_file


def test_readme_has_required_sections() -> None:
    readme = build_fastapi_todo_files()["README.md"]
    for section in ("## Setup", "## Run the server", "## Run the tests", "## API examples"):
        assert section in readme
    assert "Known limitations" in readme
    assert "No authentication" in readme


def test_no_secret_material_in_generated_files() -> None:
    from shared.sdk.workspace_operator.safety import contains_secret

    for content in build_fastapi_todo_files().values():
        assert contains_secret(content) is False


def test_file_type_classification() -> None:
    assert file_type_for("tests/test_todos.py") == "test"
    assert file_type_for("README.md") == "documentation"
    assert file_type_for("app/main.py") == "source"
    assert file_type_for("pyproject.toml") == "config"
