"""Step 59 -- sandbox draft branch naming policy.

Deterministically builds `sandbox/ai-agents/{project_key}/{work_item_key}/{cid}` from
sanitized inputs. The result can never be a protected branch and never contains a
path-traversal segment, space, or shell metacharacter.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BRANCH_YAML = ROOT / "infra" / "github" / "sandbox-draft-branch-policy.yaml"

_SANITIZE_RE = re.compile(r"[^a-z0-9-]+")
_DASHES_RE = re.compile(r"-{2,}")


class BranchPolicyError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_branch_policy() -> dict:
    data = yaml.safe_load(BRANCH_YAML.read_text(encoding="utf-8")) or {}
    return data.get("sandboxDraftBranch", {}) or {}


def sanitize(value: str) -> str:
    """Lowercase, replace any non `[a-z0-9-]` run with '-', collapse + strip dashes."""
    v = _SANITIZE_RE.sub("-", (value or "").strip().lower())
    v = _DASHES_RE.sub("-", v).strip("-")
    return v


def generate_branch_name(project_key: str, work_item_key: str, correlation_id: str) -> str:
    policy = load_branch_policy()
    prefix = str(policy.get("prefix", "sandbox/ai-agents/"))
    cid_len = int(policy.get("shortCorrelationIdLength", 12))
    proj = sanitize(project_key) or "project"
    wi = sanitize(work_item_key) or "item"
    cid = sanitize(correlation_id)[:cid_len] or "0"
    name = f"{prefix}{proj}/{wi}/{cid}"
    max_len = int(policy.get("maxLength", 200))
    if len(name) > max_len:
        name = name[:max_len].rstrip("-/")
    validate_branch_name(name)
    return name


def validate_branch_name(name: str) -> None:
    policy = load_branch_policy()
    prefix = str(policy.get("prefix", "sandbox/ai-agents/"))
    if not name.startswith(prefix):
        raise BranchPolicyError(f"branch must start with {prefix!r}")
    if ".." in name:
        raise BranchPolicyError("path traversal not allowed")
    if any(c.isspace() for c in name):
        raise BranchPolicyError("spaces not allowed")
    if re.search(r"[;|&$`()<>\\]", name):
        raise BranchPolicyError("shell metacharacters not allowed")
    last = name.rsplit("/", 1)[-1]
    forbidden_names = set(policy.get("forbiddenBranchNames", []) or [])
    if name in forbidden_names or last in forbidden_names:
        raise BranchPolicyError("protected branch name not allowed")
    for p in policy.get("forbiddenPrefixes", []) or []:
        # the first path segment after the sandbox prefix must not be a forbidden prefix
        tail = name[len(prefix) :]
        if tail.startswith(p):
            raise BranchPolicyError(f"forbidden branch prefix: {p}")
