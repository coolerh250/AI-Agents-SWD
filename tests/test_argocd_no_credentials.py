"""Step 51.3 -- no credentials / Secret resources in GitOps manifests."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITOPS = ROOT / "infra" / "gitops"
ARGOCD = GITOPS / "argocd"
CRED = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|ssh-rsa |xox[baprs]-|AKIA[0-9A-Z]{16}|"
    r"(password|token|bearer)\s*[:=]\s*\S)",
    re.IGNORECASE,
)


def test_no_credential_strings_in_argocd() -> None:
    for p in ARGOCD.rglob("*.yaml"):
        assert not CRED.search(p.read_text(encoding="utf-8")), p.name


def test_no_secret_resource() -> None:
    for p in GITOPS.rglob("*.yaml"):
        for d in yaml.safe_load_all(p.read_text(encoding="utf-8")):
            if isinstance(d, dict):
                assert d.get("kind") != "Secret", p.name


def test_credential_dirs_absent() -> None:
    for d in ("credentials", "secrets", "clusters"):
        assert not (GITOPS / d).exists(), d
