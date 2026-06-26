"""Step 57 -- project registry rules."""

from __future__ import annotations

from shared.sdk.projects import registry


def test_project_key_deterministic() -> None:
    a = registry.project_key_from_name("My Cool Project")
    b = registry.project_key_from_name("My Cool Project")
    assert a == b
    assert a.startswith("PRJ-")
    assert " " not in a


def test_dispatch_guards() -> None:
    assert registry.can_dispatch_new_work_item("active") is True
    assert registry.can_dispatch_new_work_item("archived") is False
    assert registry.can_dispatch_new_work_item("completed") is False
    assert registry.can_auto_dispatch("paused") is False
    assert registry.can_add_active_work_item("completed") is False
    assert registry.can_add_active_work_item("active") is True


def test_production_not_allowed_by_default() -> None:
    assert registry.production_allowed_default() is False
