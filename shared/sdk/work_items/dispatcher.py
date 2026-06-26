"""Step 57 -- work-item dispatch target resolution (deterministic).

Loads infra/delivery/work-item-dispatch-policy.yaml. Resolves a work type to an
internal agent target + stream, refuses production_effect direct dispatch and any
forbidden target (GitHub write / ArgoCD sync / production executor / external send),
and builds the dispatch event payload. No real side effects.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
DISPATCH_YAML = ROOT / "infra" / "delivery" / "work-item-dispatch-policy.yaml"


class DispatchError(ValueError):
    """Raised when a dispatch is refused by policy."""


@lru_cache(maxsize=1)
def _policy() -> dict[str, Any]:
    data = yaml.safe_load(DISPATCH_YAML.read_text(encoding="utf-8")) or {}
    return data.get("workItemDispatchPolicy", {})


def target_agents() -> list[str]:
    return list(_policy().get("targetAgents", []))


def forbidden_targets() -> set[str]:
    return set(_policy().get("forbiddenTargets", []))


def _rule_for(work_type: str) -> dict[str, str] | None:
    for rule in _policy().get("rules", []):
        if rule.get("workType") == work_type:
            return rule
    return None


def resolve_target(work_type: str) -> tuple[str, str]:
    """Return (target_agent, target_stream) for a work type, or raise DispatchError."""
    rule = _rule_for(work_type)
    if rule is None:
        raise DispatchError(f"no dispatch rule for work type: {work_type}")
    agent = rule["target"]
    if agent in forbidden_targets() or agent not in target_agents():
        raise DispatchError(f"target not allowed: {agent}")
    return agent, rule["stream"]


def build_dispatch_event(
    *,
    project_id: str,
    project_key: str,
    work_item_id: str,
    work_item_key: str,
    dispatch_key: str,
    work_type: str,
    correlation_id: str,
    production_effect: bool = False,
) -> dict[str, Any]:
    """Build the dispatch event payload. Refuses production_effect direct dispatch."""
    if production_effect:
        raise DispatchError(
            "production_effect work items must go to waiting_approval, not dispatch"
        )
    agent, stream = resolve_target(work_type)
    return {
        "project_id": project_id,
        "project_key": project_key,
        "work_item_id": work_item_id,
        "work_item_key": work_item_key,
        "dispatch_key": dispatch_key,
        "target_agent": agent,
        "target_stream": stream,
        "correlation_id": correlation_id,
        "production_effect": False,
        # External side effects are always disabled in this stage.
        "github_write": False,
        "argocd_sync": False,
        "external_notification_send": False,
        "production_action": False,
    }
