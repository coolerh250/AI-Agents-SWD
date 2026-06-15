"""Stage 50 -- admin console aggregate API performs no writes / side effects."""

from __future__ import annotations

import admin_console_api
import pytest
from admin_console_helpers import wire_admin_console


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)


async def test_read_endpoints_never_write(tmp_path, monkeypatch) -> None:
    result, stores = await wire_admin_console(tmp_path, monkeypatch)

    # Arm tripwires on every mutating store method.
    def _tripwire(name):
        async def _boom(*a, **k):
            raise AssertionError(f"admin console called a write method: {name}")

        return _boom

    for store_key in ("project", "pilot", "package"):
        store = stores[store_key]
        for attr in dir(store):
            if attr.startswith(("create_", "update_", "set_", "delete_")):
                monkeypatch.setattr(store, attr, _tripwire(f"{store_key}.{attr}"))

    # All read endpoints must run without tripping a write.
    await admin_console_api.overview()
    await admin_console_api.projects()
    await admin_console_api.project_detail(result.project_id)
    await admin_console_api.latest_delivery_state()
    await admin_console_api.safety_summary()
    await admin_console_api.regression_summary()


def test_router_has_only_get_routes() -> None:
    for route in admin_console_api.router.routes:
        methods = getattr(route, "methods", set()) or set()
        # Starlette includes HEAD automatically alongside GET; nothing else allowed.
        assert methods <= {"GET", "HEAD"}, (route.path, methods)
