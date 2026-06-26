"""Step 59 -- sandbox repository allowlist resolution.

A request carries a repository *key*; this module resolves it to an allowlisted
sandbox repository. An unknown key, a disallowed base branch, or a head branch that
does not match the allowed prefix is rejected -- arbitrary owner/repo is impossible.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .models import SandboxRepo

ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_YAML = ROOT / "infra" / "github" / "sandbox-repository-allowlist.yaml"


@lru_cache(maxsize=1)
def _repos() -> dict[str, SandboxRepo]:
    data = yaml.safe_load(ALLOWLIST_YAML.read_text(encoding="utf-8")) or {}
    out: dict[str, SandboxRepo] = {}
    for r in data.get("repositories", []) or []:
        key = str(r.get("key", "")).strip()
        if not key:
            continue
        out[key] = SandboxRepo(
            key=key,
            owner=str(r.get("owner", "")).strip(),
            repo=str(r.get("repo", "")).strip(),
            allowed=bool(r.get("allowed", False)),
            sandbox_only=bool(r.get("sandboxOnly", False)),
            allowed_base_branches=tuple(r.get("allowedBaseBranches", []) or []),
            allowed_head_prefixes=tuple(r.get("allowedHeadPrefix", []) or []),
            allow_draft_pr=bool(r.get("allowDraftPR", False)),
            allow_merge=bool(r.get("allowMerge", False)),
            allow_ready_for_review=bool(r.get("allowReadyForReview", False)),
            allow_release=bool(r.get("allowRelease", False)),
            allow_deployment=bool(r.get("allowDeployment", False)),
            allow_workflow_dispatch=bool(r.get("allowWorkflowDispatch", False)),
        )
    return out


def list_repositories() -> list[SandboxRepo]:
    return list(_repos().values())


def resolve_repository(repository_key: str) -> SandboxRepo | None:
    repo = _repos().get((repository_key or "").strip())
    if repo is None or not repo.allowed or not repo.sandbox_only:
        return None
    return repo


def base_branch_allowed(repo: SandboxRepo, base: str) -> bool:
    return base in repo.allowed_base_branches


def head_prefix_allowed(repo: SandboxRepo, head: str) -> bool:
    return any(head.startswith(p) for p in repo.allowed_head_prefixes)
