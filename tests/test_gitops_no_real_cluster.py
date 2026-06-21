"""Step 51.3 -- no real cluster endpoint / not-applied markers."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITOPS = ROOT / "infra" / "gitops"
REAL_IP = re.compile(r"https://([0-9]{1,3}\.){3}[0-9]{1,3}")
CLOUD = re.compile(r"\.(eks\.amazonaws\.com|gke\.|azmk8s\.io|googleapis\.com)", re.IGNORECASE)


def test_no_real_ip_or_cloud_endpoint() -> None:
    for p in GITOPS.rglob("*.yaml"):
        raw = p.read_text(encoding="utf-8")
        assert not REAL_IP.search(raw), p.name
        assert not CLOUD.search(raw), p.name


def test_catalog_declares_not_connected() -> None:
    meta = yaml.safe_load((GITOPS / "gitops-environments.yaml").read_text(encoding="utf-8"))["meta"]
    assert meta["clusterConnected"] is False
    assert meta["syncPerformed"] is False


def test_only_placeholder_servers() -> None:
    for p in (GITOPS / "argocd").rglob("*.yaml"):
        for d in yaml.safe_load_all(p.read_text(encoding="utf-8")):
            if isinstance(d, dict) and d.get("kind") == "Application":
                server = d["spec"]["destination"]["server"]
                assert server == "https://kubernetes.default.svc" or server.endswith(
                    ".invalid"
                ), server
