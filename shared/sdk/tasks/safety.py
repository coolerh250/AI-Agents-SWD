"""Step 66B.1 -- task API safety fields, spliced into GET /operations/safety.

No DB, no cluster, no external call. task_api_test_auth_enabled reflects the
TASK_API_TEST_AUTH_ENABLED env flag -- the fail-closed test-only auth gate that
stands in for a real identity/session model (documented gap, see
docs/test/step66b1-known-gaps.md). All dangerous-effect flags are hard False --
66B.1 never dispatches a workflow or performs an external write.
"""

from __future__ import annotations

import os
from typing import Any


def tasks_safety_fields() -> dict[str, Any]:
    test_auth_enabled = (
        os.environ.get("TASK_API_TEST_AUTH_ENABLED", "false").strip().lower() == "true"
    )
    return {
        "task_api_enabled": True,
        "task_api_write_enabled": True,
        "task_api_test_auth_enabled": test_auth_enabled,
        "task_api_workflow_dispatch_enabled": False,
        "task_api_production_effect_enabled": False,
        "task_api_external_integration_enabled": False,
        "task_api_github_write_enabled": False,
        "task_api_discord_send_enabled": False,
        "task_api_llm_call_enabled": False,
        # Step 66B.3 hardening: every RBAC denial (403) now emits a task_rbac_denied
        # audit event (see shared/sdk/tasks/audit_events.py + task_api.py::_deny).
        "task_api_rbac_denied_audit_enabled": True,
    }


__all__ = ["tasks_safety_fields"]
