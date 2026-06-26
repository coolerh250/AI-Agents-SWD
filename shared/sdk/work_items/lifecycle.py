"""Step 57 -- work-item delivery lifecycle (deterministic state machine).

Loads infra/delivery/work-item-lifecycle.yaml and validates transitions. Pure
logic -- no DB, no cluster, no production action. production_effect work items must
go to waiting_approval, never dispatched directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
LIFECYCLE_YAML = ROOT / "infra" / "delivery" / "work-item-lifecycle.yaml"


@lru_cache(maxsize=1)
def _policy() -> dict[str, Any]:
    data = yaml.safe_load(LIFECYCLE_YAML.read_text(encoding="utf-8")) or {}
    return data.get("workItemLifecycle", {})


def states() -> list[str]:
    return list(_policy().get("states", []))


def initial_state() -> str:
    return str(_policy().get("initialState", "created"))


def terminal_states() -> set[str]:
    return set(_policy().get("terminalStates", []))


def is_terminal(state: str) -> bool:
    return state in terminal_states()


def transitions() -> dict[str, list[str]]:
    return dict(_policy().get("transitions", {}))


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in transitions().get(from_state, [])


def rules() -> dict[str, Any]:
    return dict(_policy().get("rules", {}))


def validate_transition(from_state: str, to_state: str) -> None:
    """Raise ValueError if the transition is not allowed."""
    if from_state not in states():
        raise ValueError(f"unknown from_state: {from_state}")
    if to_state not in states():
        raise ValueError(f"unknown to_state: {to_state}")
    if not can_transition(from_state, to_state):
        raise ValueError(f"illegal transition: {from_state} -> {to_state}")


def next_state_for_dispatch(production_effect: bool) -> str:
    """ready_for_dispatch resolves to waiting_approval for production_effect items,
    else dispatched. Never dispatch a production_effect item directly."""
    if production_effect and rules().get("productionEffectRequiresApproval", True):
        return "waiting_approval"
    return "dispatched"
