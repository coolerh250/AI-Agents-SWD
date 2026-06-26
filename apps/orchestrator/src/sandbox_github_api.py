"""Step 59 (Stage 61A) -- sandbox GitHub draft PR API.

Read endpoints are GET-only + redacted (policy / allowlist / requests / detail / safety
/ readiness). The single write endpoint creates a *sandbox draft PR request* and reuses
the existing operator auth + CSRF + audit; it requires a reason and a repository *key*
(never an arbitrary owner/repo), and a production_effect work item is never turned into
a PR. There is NO merge / ready-for-review / workflow-dispatch / non-sandbox / token
endpoint. The GitHub token is never returned.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from operator_actions_api import _AuthError, _audit, _authenticate, _require_csrf

from shared.sdk.projects import ProjectStore
from shared.sdk.sandbox_github import (
    SandboxDraftPrStore,
    SandboxGitHubClient,
    sandbox_github_safety_fields,
)
from shared.sdk.sandbox_github import allowlist as _allowlist
from shared.sdk.sandbox_github import policy as _policy
from shared.sdk.work_items import WorkItemStore

router = APIRouter(prefix="/operations/github", tags=["sandbox-github"])

_projects = ProjectStore()
_items = WorkItemStore()
_store = SandboxDraftPrStore()


def _err(status: int, reason: str) -> dict:
    return {
        "status": "policy_blocked" if status == 403 else "error",
        "reason": reason,
        "production_executed": False,
        "merge_performed": False,
        "ready_for_review_performed": False,
        "workflow_dispatch_performed": False,
        "non_sandbox_repo_write_performed": False,
    }


# ---------------------------------------------------------------------------
# Read endpoints (GET-only, redacted, no token)
# ---------------------------------------------------------------------------
@router.get("/sandbox-draft-pr/policy")
async def get_policy() -> dict:
    p = _policy.load_policy()
    return {
        "production_ready": False,
        "enabled": bool(p.get("enabled", False)),
        "default_mode": p.get("defaultMode"),
        "allowed_modes": p.get("allowedMode", []),
        "allow_merge": bool(p.get("allowMerge", False)),
        "allow_ready_for_review": bool(p.get("allowReadyForReview", False)),
        "allow_non_sandbox_repo": bool(p.get("allowNonSandboxRepo", False)),
        "allow_production_branch": bool(p.get("allowProductionBranch", False)),
        "allow_workflow_dispatch": bool(p.get("allowWorkflowDispatch", False)),
        "allow_issue_write": bool(p.get("allowIssueWrite", False)),
        "allow_release_write": bool(p.get("allowReleaseWrite", False)),
        "allow_deployment_write": bool(p.get("allowDeploymentWrite", False)),
        "forbidden_base_branches": p.get("forbiddenBaseBranches", []),
    }


@router.get("/sandbox-draft-pr/allowlist")
async def get_allowlist() -> dict:
    repos = [
        {
            "key": r.key,
            "owner": r.owner,
            "repo": r.repo,
            "sandbox_only": r.sandbox_only,
            "allowed_base_branches": list(r.allowed_base_branches),
            "allowed_head_prefixes": list(r.allowed_head_prefixes),
            "allow_draft_pr": r.allow_draft_pr,
            "allow_merge": r.allow_merge,
            "allow_release": r.allow_release,
            "allow_deployment": r.allow_deployment,
        }
        for r in _allowlist.list_repositories()
    ]
    return {"production_ready": False, "repositories": repos}


@router.get("/sandbox-draft-pr/safety")
async def get_safety() -> dict:
    count = 0
    try:
        count = await _store.count_created()
    except Exception:  # noqa: BLE001 -- DB unavailable -> config-driven posture, count 0
        count = 0
    return {"production_ready": False, **sandbox_github_safety_fields(draft_pr_created_count=count)}


@router.get("/sandbox-draft-pr/readiness")
async def get_readiness() -> dict:
    return {
        "production_ready": False,
        "default_mode": _policy.default_mode(),
        "live_mode_requested_enabled": _policy.live_mode_requested_enabled(),
        "live_mode_effective": _policy.live_mode_effective(),
        "credential_present": _policy.has_credential(),
        "blocked_reason": _policy.resolve_mode("live_sandbox")[1],
    }


@router.get("/sandbox-draft-pr/requests")
async def list_requests() -> dict:
    try:
        rows = await _store.list_requests()
    except Exception:  # noqa: BLE001
        return {"production_ready": False, "available": False, "requests": []}
    return {"production_ready": False, "requests": rows}


@router.get("/sandbox-draft-pr")
async def list_requests_root() -> dict:
    return await list_requests()


@router.get("/sandbox-draft-pr/{request_id}")
async def get_request(request_id: str) -> dict:
    try:
        rec = await _store.get_request(request_id)
    except Exception:  # noqa: BLE001
        return {"status": "unavailable"}
    return rec or {"status": "not_found"}


# ---------------------------------------------------------------------------
# Write endpoint (auth + CSRF + reason + audit) -- sandbox draft PR request only
# ---------------------------------------------------------------------------
@router.post("/sandbox-draft-pr")
async def request_draft_pr(request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")
    repository_key = (body.get("repository_key") or "").strip()
    if not repository_key:
        return _err(400, "repository_key_required")
    project_id = (body.get("project_id") or "").strip()
    work_item_id = (body.get("work_item_id") or "").strip()
    if not project_id or not work_item_id:
        return _err(400, "project_id_and_work_item_id_required")

    proj = await _projects.get_project(project_id)
    if not proj:
        return _err(404, "project_not_found")
    wi = await _items.get_work_item(work_item_id)
    if not wi:
        return _err(404, "work_item_not_found")

    correlation_id = uuid.uuid4().hex
    client = SandboxGitHubClient(actor=ctx["identity_key"], role=ctx["role"], reason=reason)
    result = client.request_draft_pr(
        repository_key=repository_key,
        project_id=project_id,
        project_key=proj.get("project_key") or proj.get("name") or "project",
        work_item_id=work_item_id,
        work_item_key=wi.get("work_item_key") or "item",
        work_item_title=wi.get("title") or "work item",
        correlation_id=correlation_id,
        base_branch=body.get("base_branch"),
        requested_mode=body.get("mode"),
        production_effect=bool(wi.get("production_effect", False)),
    )

    audit_event_id = uuid.uuid4().hex
    record = None
    try:
        record = await _store.create_request(
            project_id=project_id,
            project_key=proj.get("project_key"),
            work_item_id=work_item_id,
            work_item_key=wi.get("work_item_key"),
            dispatch_id=None,
            correlation_id=correlation_id,
            repository_key=repository_key,
            branch_name=result.branch_name,
            draft_pr_url=result.draft_pr_url,
            draft_pr_number=result.draft_pr_number,
            mode=result.mode,
            status=result.status,
            audit_event_id=audit_event_id,
        )
    except Exception:  # noqa: BLE001 -- persistence best-effort; never fabricate success
        record = None

    await _audit(
        "sandbox_github_draft_pr",
        f"sandbox draft PR {result.status} for {wi.get('work_item_key')} ({result.mode})",
        result.status,
        {
            "project_id": project_id,
            "work_item_id": work_item_id,
            "repository_key": repository_key,
            "mode": result.mode,
            "correlation_id": correlation_id,
            "actor": ctx["identity_key"],
            "reason": reason,
            "production_executed": False,
        },
    )
    out = result.to_dict()
    out["request_id"] = (record or {}).get("id")
    out["audit_event_id"] = audit_event_id
    return out


__all__ = ["router"]
