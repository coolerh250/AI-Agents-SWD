"""Step 62 -- deployment authorization boundary loading.

Makes explicit what the readiness gate may / may not authorize. An operator review request
is never a production approval; rollout planning is never rollout execution.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
MODEL_YAML = ROOT / "infra" / "readiness" / "deployment-authorization-boundary-model.yaml"


@lru_cache(maxsize=1)
def load_boundary() -> dict[str, Any]:
    data = yaml.safe_load(MODEL_YAML.read_text(encoding="utf-8")) or {}
    return data.get("deploymentAuthorizationBoundary", {}) or {}


def may_authorize() -> list[str]:
    return list(load_boundary().get("mayAuthorize", []) or [])


def may_not_authorize() -> list[str]:
    return list(load_boundary().get("mayNotAuthorize", []) or [])


def operator_review_is_approval() -> bool:
    return bool(load_boundary().get("operatorReviewRequestIsApproval", False))
