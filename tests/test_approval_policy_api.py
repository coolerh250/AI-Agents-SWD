"""Stage 31 -- approval policy API surface tests.

Verifies the routes are registered + the create-policy validator
rejects malformed delegated / per_feature / per_stage payloads BEFORE
talking to the DB.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).resolve().parents[1]


def _load_api_module() -> ModuleType:
    src = _ROOT / "apps" / "orchestrator" / "src" / "approval_policy_api.py"
    spec = importlib.util.spec_from_file_location("approval_policy_api_test", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_router_registers_expected_paths() -> None:
    mod = _load_api_module()
    paths = {r.path for r in mod.router.routes}
    for expected in (
        "/approval-policies",
        "/approval-policies/{policy_id}",
        "/approval-policies/{policy_id}/activate",
        "/approval-policies/{policy_id}/revoke",
        "/approval-policies/{policy_id}/decisions",
        "/llm/proposals/{proposal_id}/approval/request",
        "/llm/proposals/{proposal_id}/approval/approve",
        "/llm/proposals/{proposal_id}/approval/reject",
        "/llm/proposals/{proposal_id}/promote",
    ):
        assert expected in paths, expected


def test_validate_payload_rejects_unknown_mode() -> None:
    mod = _load_api_module()
    import pytest
    from fastapi import HTTPException

    payload = mod.CreatePolicyIn(task_id="t1", approval_mode="ridiculous")
    with pytest.raises(HTTPException) as exc:
        mod._validate_create_payload(payload)
    assert exc.value.status_code == 400
    assert "unknown approval_mode" in str(exc.value.detail)


def test_validate_payload_rejects_delegated_missing_constraints() -> None:
    mod = _load_api_module()
    import pytest
    from fastapi import HTTPException

    payload = mod.CreatePolicyIn(
        task_id="t1",
        approval_mode="delegated",
    )
    with pytest.raises(HTTPException) as exc:
        mod._validate_create_payload(payload)
    assert exc.value.status_code == 400
    assert "delegated_missing" in str(exc.value.detail)


def test_validate_payload_rejects_per_feature_missing_actions() -> None:
    mod = _load_api_module()
    import pytest
    from fastapi import HTTPException

    payload = mod.CreatePolicyIn(
        task_id="t1",
        approval_mode="per_feature",
        allowed_paths=["docs/generated/"],
    )
    with pytest.raises(HTTPException) as exc:
        mod._validate_create_payload(payload)
    assert exc.value.status_code == 400
    assert "per_feature_missing" in str(exc.value.detail)


def test_validate_payload_rejects_per_stage_missing_stages() -> None:
    mod = _load_api_module()
    import pytest
    from fastapi import HTTPException

    payload = mod.CreatePolicyIn(
        task_id="t1",
        approval_mode="per_stage",
        allowed_actions=["llm_proposal_promote"],
        allowed_paths=["docs/generated/"],
    )
    with pytest.raises(HTTPException) as exc:
        mod._validate_create_payload(payload)
    assert exc.value.status_code == 400
    assert "per_stage_missing:allowed_stages" in str(exc.value.detail)


def test_validate_payload_accepts_complete_delegated() -> None:
    mod = _load_api_module()
    payload = mod.CreatePolicyIn(
        task_id="t1",
        approval_mode="delegated",
        allowed_actions=["llm_proposal_promote"],
        allowed_paths=["docs/generated/"],
        denied_paths=[".env"],
        max_actions=5,
        max_files_changed=3,
        max_auto_fix_attempts=2,
        expires_at="2030-01-01T00:00:00+00:00",
    )
    # No exception means the validator accepted the payload.
    mod._validate_create_payload(payload)


def test_validate_payload_accepts_complete_per_action() -> None:
    mod = _load_api_module()
    payload = mod.CreatePolicyIn(task_id="t1", approval_mode="per_action")
    mod._validate_create_payload(payload)
