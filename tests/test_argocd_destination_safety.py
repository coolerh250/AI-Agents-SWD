"""Step 51.3 -- destinations are safe placeholders (no real cluster/namespace)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ARGOCD = ROOT / "infra" / "gitops" / "argocd"
SAFE = re.compile(r"^https://kubernetes\.default\.svc$|^https://[a-z0-9.-]+\.invalid$")
REAL_IP = re.compile(r"https://([0-9]{1,3}\.){3}[0-9]{1,3}")


def _apps() -> list[dict]:
    out = []
    for p in ARGOCD.rglob("*.yaml"):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("kind") == "Application":
            out.append(d)
    return out


def test_destination_servers_are_placeholders() -> None:
    for a in _apps():
        server = a["spec"]["destination"]["server"]
        assert SAFE.match(server), (a["metadata"]["name"], server)


def test_no_real_ip_endpoints() -> None:
    for p in ARGOCD.rglob("*.yaml"):
        assert not REAL_IP.search(p.read_text(encoding="utf-8")), p.name


def test_no_real_production_namespace() -> None:
    for a in _apps():
        ns = a["spec"]["destination"].get("namespace", "")
        if "production" in ns:
            assert "placeholder" in ns, a["metadata"]["name"]


def test_no_wildcard_destination() -> None:
    for a in _apps():
        assert a["spec"]["destination"]["server"] != "*"
