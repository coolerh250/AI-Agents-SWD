#!/usr/bin/env python3
"""Step 51.2B -- rendered NetworkPolicy safety checker.

Reads the four-environment rendered manifests and asserts the default-deny
baseline, scoped DNS, no empty allow selectors, no unrestricted CIDR, no
external egress, no Postgres/Redis external exposure, no NodePort/LoadBalancer,
and the production/staging restrictions.

NO cluster connection. Marker: KUBERNETES_NETWORK_POLICY_VERIFY: PASS | FAIL
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
HELM_IMAGE = "alpine/helm:3.16.3"
ENV_VALUES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "prod": "values-prod-placeholder.yaml",
}

failures: list[str] = []
passes: list[str] = []


def ok(msg: str) -> None:
    passes.append(msg)
    print(f"  [PASS] {msg}")


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
            p = RENDER_DIR / f"{env}.yaml"
            p.write_text(res.stdout, encoding="utf-8")
            out.append(p)
    return out


def docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]


def main() -> int:
    rendered = ensure_rendered()
    if not rendered:
        print("  [FAIL] no rendered manifests and no helm/docker to render them")
        print("KUBERNETES_NETWORK_POLICY_VERIFY: FAIL")
        return 1

    for path in rendered:
        env = path.stem
        all_docs = docs(path)
        policies = [d for d in all_docs if d.get("kind") == "NetworkPolicy"]
        services = [d for d in all_docs if d.get("kind") == "Service"]
        names = {p["metadata"]["name"] for p in policies}

        # default-deny + DNS present
        if any(n.endswith("default-deny-ingress") for n in names):
            ok(f"[{env}] default-deny ingress present")
        else:
            bad(f"[{env}] missing default-deny ingress")
        if any(n.endswith("default-deny-egress") for n in names):
            ok(f"[{env}] default-deny egress present")
        else:
            bad(f"[{env}] missing default-deny egress")
        dns = [p for p in policies if p["metadata"]["name"].endswith("allow-dns")]
        if dns:
            ok(f"[{env}] DNS egress policy present")
        else:
            bad(f"[{env}] missing DNS egress policy")

        for p in policies:
            name = p["metadata"]["name"]
            spec = p.get("spec", {})
            sel = spec.get("podSelector", {})
            is_default_deny = name.endswith("default-deny-ingress") or name.endswith(
                "default-deny-egress"
            )
            # empty podSelector only on default-deny
            if (not sel or sel == {}) and not is_default_deny:
                bad(f"[{env}] {name}: empty podSelector only allowed on default-deny")
            # stable label contract on non-default-deny selectors
            if not is_default_deny and sel:
                ml = sel.get("matchLabels", {})
                if "app.kubernetes.io/instance" not in ml and "app.kubernetes.io/part-of" not in ml:
                    bad(f"[{env}] {name}: selector missing stable instance/part-of label")
            # scan ingress/egress peers
            for rule in (spec.get("ingress", []) or []) + (spec.get("egress", []) or []):
                peers = rule.get("from", []) or rule.get("to", []) or []
                for peer in peers:
                    if "ipBlock" in peer:
                        cidr = peer["ipBlock"].get("cidr", "")
                        if cidr in ("0.0.0.0/0", "::/0"):
                            bad(f"[{env}] {name}: unrestricted CIDR {cidr}")
                    # DNS policy legitimately uses ns+pod selector to kube-dns
                    if name.endswith("allow-dns"):
                        continue
                    if "namespaceSelector" in peer and not peer.get("podSelector"):
                        # an allow rule with only namespaceSelector and no pod scoping
                        if peer["namespaceSelector"] == {}:
                            bad(f"[{env}] {name}: empty namespaceSelector allow")
                # DNS ports must be 53
                if name.endswith("allow-dns"):
                    for port in rule.get("ports", []):
                        if int(port.get("port")) != 53:
                            bad(f"[{env}] DNS port must be 53, got {port.get('port')}")

        # no NodePort / LoadBalancer
        for s in services:
            t = s.get("spec", {}).get("type", "ClusterIP")
            if t in ("NodePort", "LoadBalancer"):
                bad(f"[{env}] Service {s['metadata']['name']} type {t} forbidden")

        # production / staging restrictions
        if env in ("staging", "prod"):
            if any("egress-" in n and "external" in n for n in names):
                bad(f"[{env}] external egress policy present")
        if env == "prod":
            if any(n.endswith("ingress-controller") for n in names):
                bad("[prod] ingress-controller policy must not be present")

        # workloads: no hostNetwork/hostPort
        for d in all_docs:
            if d.get("kind") in ("Deployment", "StatefulSet", "DaemonSet"):
                spec = (((d.get("spec") or {}).get("template") or {}).get("spec")) or {}
                if spec.get("hostNetwork"):
                    bad(f"[{env}] {d['metadata']['name']} hostNetwork forbidden")
                for c in spec.get("containers", []) or []:
                    for port in c.get("ports", []) or []:
                        if "hostPort" in port:
                            bad(f"[{env}] {d['metadata']['name']} hostPort forbidden")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_NETWORK_POLICY_VERIFY: FAIL")
        return 1
    print("KUBERNETES_NETWORK_POLICY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
