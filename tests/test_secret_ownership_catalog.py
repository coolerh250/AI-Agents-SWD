"""Step 53 -- secret ownership catalog (roles only)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-ownership-catalog.yaml"
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_owners_use_roles_not_names() -> None:
    text = F.read_text(encoding="utf-8")
    assert _EMAIL.search(text) is None  # no real person emails
    for o in _d()["owners"]:
        assert o["systemOwner"].endswith("_owner")


def test_production_approval_required() -> None:
    for o in _d()["owners"]:
        assert o["productionApprovalRequired"] is True


def test_break_glass_dual_approval_modeled() -> None:
    bg = next(o for o in _d()["owners"] if o["secretKey"] == "break_glass_credential")
    assert bg["dualApprovalRequired"] is True
    assert _d()["policy"]["breakGlassDualApprovalModeledNotEnabled"] is True


def test_owner_roles_listed() -> None:
    roles = _d()["ownerRoles"]
    for r in ("platform_security_owner", "identity_owner", "backup_owner", "gitops_owner"):
        assert r in roles
