#!/usr/bin/env python3
"""Step 51.2B -- service connectivity coverage verifier.

For every required internal edge expected in an environment, asserts a matching
egress allow on the source AND ingress allow on the target (selector + port).
Reports coverage and fails on missing or unexpected edges.

NO cluster connection. Marker: KUBERNETES_SERVICE_CONNECTIVITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART_REL = "infra/kubernetes/charts/ai-agents-platform"
RENDER_DIR = ROOT / ".runtime" / "kubernetes-rendered"
CATALOG = ROOT / "infra" / "kubernetes" / "network-connectivity-catalog.yaml"
HELM_IMAGE = "alpine/helm:3.16.3"
ENV_VALUES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "prod": "values-prod-placeholder.yaml",
}
# catalog environments use full names; rendered files use short stems
ENV_NAME = {"dev": "dev", "test": "test", "staging": "staging", "prod": "production"}

failures: list[str] = []


def bad(msg: str) -> None:
    failures.append(msg)
    print(f"  [FAIL] {msg}")


def ensure_rendered() -> list[Path]:
    existing = sorted(RENDER_DIR.glob("*.yaml"))
    if existing:
        return existing
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    if shutil.which("helm"):
        base = ["helm"]
    elif shutil.which("docker"):
        base = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", "-w", "/work", HELM_IMAGE]
    else:
        return []
    out: list[Path] = []
    for env, vf in ENV_VALUES.items():
        res = subprocess.run(
            base + ["template", "ai-agents-platform", CHART_REL, "-f", f"{CHART_REL}/{vf}"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if res.returncode == 0:
            (RENDER_DIR / f"{env}.yaml").write_text(res.stdout, encoding="utf-8")
            out.append(RENDER_DIR / f"{env}.yaml")
    return out


def parse_policies(path: Path):
    egress = set()
    ingress = set()
    for d in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if not isinstance(d, dict) or d.get("kind") != "NetworkPolicy":
            continue
        spec = d.get("spec", {})
        src_sel = spec.get("podSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name")
        for rule in spec.get("egress", []) or []:
            ports = [int(p["port"]) for p in rule.get("ports", []) if "port" in p]
            for peer in rule.get("to", []) or []:
                tgt = (
                    peer.get("podSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name")
                )
                if tgt and src_sel:
                    for port in ports:
                        egress.add((src_sel, tgt, port))
        for rule in spec.get("ingress", []) or []:
            ports = [int(p["port"]) for p in rule.get("ports", []) if "port" in p]
            for peer in rule.get("from", []) or []:
                src = (
                    peer.get("podSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name")
                )
                if src and src_sel:
                    for port in ports:
                        ingress.add((src, src_sel, port))  # (source, target, port)
    return egress, ingress


def main() -> int:
    rendered = ensure_rendered()
    if not rendered:
        print("  [FAIL] no rendered manifests and no helm/docker to render them")
        print("KUBERNETES_SERVICE_CONNECTIVITY_VERIFY: FAIL")
        return 1

    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    cat_edges = catalog["internalEdges"]

    total_required = covered_e = covered_i = fully = 0
    for path in rendered:
        env = path.stem
        full_env = ENV_NAME[env]
        expected = {
            (e["source"], e["target"], int(e["port"]))
            for e in cat_edges
            if full_env in e["environments"]
        }
        egress, ingress = parse_policies(path)
        all_policy_edges = egress | ingress

        missing = []
        for edge in expected:
            total_required += 1
            has_e = edge in egress
            has_i = edge in ingress
            covered_e += 1 if has_e else 0
            covered_i += 1 if has_i else 0
            if has_e and has_i:
                fully += 1
            else:
                missing.append(
                    (edge, "egress" if not has_e else "", "ingress" if not has_i else "")
                )
        for m in missing:
            bad(f"[{env}] missing coverage for edge {m[0]} ({m[1]} {m[2]})")
        unexpected = all_policy_edges - expected
        for u in sorted(unexpected):
            bad(f"[{env}] unexpected policy edge not in catalog: {u}")
        print(
            f"  [{env}] required={len(expected)} egress={len(egress)} ingress={len(ingress)} unexpected={len(unexpected)}"
        )

    print("\n=== Coverage summary ===")
    print(f"  required_edges={total_required}")
    print(f"  covered_egress_edges={covered_e}")
    print(f"  covered_ingress_edges={covered_i}")
    print(f"  fully_covered_edges={fully}")
    print(f"  missing_edges={total_required - fully}")
    print(f"  unexpected_edges={len([f for f in failures if 'unexpected' in f])}")
    if failures:
        print("KUBERNETES_SERVICE_CONNECTIVITY_VERIFY: FAIL")
        return 1
    print("KUBERNETES_SERVICE_CONNECTIVITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
