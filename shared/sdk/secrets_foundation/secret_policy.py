"""Step 53 -- secret classification / policy loaders (read-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = ROOT / "infra" / "secrets"

SECRET_CLASSES = ("critical", "high", "medium", "public-config", "placeholder")


def _load(name: str, root: Path | None = None) -> dict[str, Any]:
    base = (root or ROOT) / "infra" / "secrets"
    return yaml.safe_load((base / name).read_text(encoding="utf-8")) or {}


def load_classification(root: Path | None = None) -> dict[str, Any]:
    return _load("secret-classification.yaml", root)


def load_redaction_policy(root: Path | None = None) -> dict[str, Any]:
    return _load("secret-redaction-policy.yaml", root)


def class_of(secret_key: str, root: Path | None = None) -> str | None:
    classes = load_classification(root).get("classes", {})
    for cls, body in classes.items():
        if secret_key in (body.get("examples") or []):
            return cls
    return None


__all__ = [
    "SECRET_CLASSES",
    "SECRETS_DIR",
    "load_classification",
    "load_redaction_policy",
    "class_of",
]
