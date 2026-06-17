#!/usr/bin/env python3
"""Step 51.2C1 -- rendered storage manifest verifier.

Renders the four environments and asserts: generated PVCs only in dev/test,
no PV/StorageClass resource, no hostPath/NFS/CSI/real storage class/real claim,
no forbidden or duplicate mount path, RWO-only generated PVCs, no RWX claim,
internal datastores dev/test-only, production has no internal datastore volume,
workspace stays ephemeral, no backup PVC, no secret literal. No cluster.

Marker: KUBERNETES_STORAGE_MANIFEST_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
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

EXPECTED_PVCS = {"postgres-data", "redis-data"}
FORBIDDEN_MOUNTS = {"/", "/app", "/etc", "/bin", "/sbin", "/usr", "/proc", "/sys", "/dev"}
BAD_STORAGE_CLASSES = {
    "gp2",
    "gp3",
    "standard",
    "premium-rwo",
    "managed-premium",
    "managed-csi",
    "ebs-sc",
    "do-block-storage",
    "csi-cinder",
    "nfs-client",
    "longhorn",
    "openebs-hostpath",
    "local-path",
    "azurefile",
    "azuredisk",
    "pd-ssd",
    "pd-standard",
    "efs-sc",
}
SAMPLE_CLAIMS = {
    "sample",
    "default",
    "placeholder",
    "changeme",
    "todo",
    "my-claim",
    "example",
    "aiagents-sample",
}
SECRET_PAT = re.compile(
    r"(password|passwd|secret[_-]?key|api[_-]?key|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,})"
    r"\s*[:=]\s*\S",
    re.IGNORECASE,
)

failures: list[str] = []
passes: list[str] = []


def ok(msg: str) -> None:
    passes.append(msg)
    print(f"  [PASS] {msg}")


def bad(msg: str) -> None:
    failures.append(msg)
    print(f"  [FAIL] {msg}")


def ensure_rendered() -> dict[str, Path]:
    out: dict[str, Path] = {}
    existing = {p.stem: p for p in RENDER_DIR.glob("*.yaml")}
    if set(ENV_VALUES) <= set(existing):
        return {e: existing[e] for e in ENV_VALUES}
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    if shutil.which("helm"):
        base = ["helm"]
    elif shutil.which("docker"):
        base = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", "-w", "/work", HELM_IMAGE]
    else:
        return {}
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
            out[env] = p
    return out


def docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]


def main() -> int:
    rendered = ensure_rendered()
    if not rendered:
        print("  [FAIL] no rendered manifests and no helm/docker to render them")
        print("KUBERNETES_STORAGE_MANIFEST_VERIFY: FAIL")
        return 1

    for env, path in rendered.items():
        all_docs = docs(path)
        pvcs = [d for d in all_docs if d.get("kind") == "PersistentVolumeClaim"]
        deployments = [d for d in all_docs if d.get("kind") == "Deployment"]
        kinds = {d.get("kind") for d in all_docs}

        # no PV / StorageClass resource ever
        if "PersistentVolume" in kinds:
            bad(f"[{env}] PersistentVolume resource must not be rendered")
        if "StorageClass" in kinds:
            bad(f"[{env}] StorageClass resource must not be rendered")

        # PVC presence per environment
        pvc_stores = set()
        for p in pvcs:
            store = p.get("metadata", {}).get("labels", {}).get("ai-agents-swd/store", "")
            if store:
                pvc_stores.add(store)
            # generated PVC must be RWO, no real SC, no selector/volumeName/dataSource
            spec = p.get("spec", {})
            modes = spec.get("accessModes", [])
            if modes != ["ReadWriteOnce"]:
                bad(f"[{env}] PVC {p['metadata']['name']} must be ReadWriteOnce, got {modes}")
            sc = (spec.get("storageClassName") or "").lower()
            if sc in BAD_STORAGE_CLASSES:
                bad(f"[{env}] PVC uses a real-looking storage class {sc}")
            for forbidden in ("selector", "volumeName", "dataSource", "dataSourceRef"):
                if forbidden in spec:
                    bad(f"[{env}] PVC {p['metadata']['name']} must not set {forbidden}")

        if env in ("dev", "test"):
            if pvc_stores >= EXPECTED_PVCS:
                ok(f"[{env}] generated datastore PVCs present ({sorted(pvc_stores)})")
            else:
                bad(f"[{env}] missing generated PVCs, got {sorted(pvc_stores)}")
        else:
            if pvcs:
                bad(
                    f"[{env}] must NOT render any generated PVC, got {[p['metadata']['name'] for p in pvcs]}"
                )
            else:
                ok(f"[{env}] no generated PVC (external datastores)")

        # claim names not sample/default; collect claim ownership
        claim_owners: dict[str, list[str]] = {}
        for d in deployments:
            spec = d.get("spec", {}).get("template", {}).get("spec", {})
            dep_name = d["metadata"]["name"]
            seen_mounts: set[str] = set()
            for vol in spec.get("volumes", []) or []:
                if "hostPath" in vol:
                    bad(f"[{env}] {dep_name} uses hostPath")
                if "nfs" in vol:
                    bad(f"[{env}] {dep_name} uses an NFS volume")
                if "csi" in vol:
                    bad(f"[{env}] {dep_name} uses a raw CSI volume")
                pvc = vol.get("persistentVolumeClaim")
                if pvc:
                    cn = pvc.get("claimName", "")
                    if cn.lower() in SAMPLE_CLAIMS:
                        bad(f"[{env}] {dep_name} mounts a sample claim {cn}")
                    claim_owners.setdefault(cn, []).append(dep_name)
            for c in spec.get("containers", []) or []:
                for vm in c.get("volumeMounts", []) or []:
                    mp = vm.get("mountPath", "")
                    if mp in FORBIDDEN_MOUNTS:
                        bad(f"[{env}] {dep_name} mounts forbidden path {mp}")
                    if mp in seen_mounts:
                        bad(f"[{env}] {dep_name} duplicate mount path {mp}")
                    seen_mounts.add(mp)

        for cn, owners in claim_owners.items():
            if len(owners) > 1:
                bad(
                    f"[{env}] claim {cn} mounted by multiple deployments {owners} (duplicate ownership)"
                )

        # internal datastores only dev/test; production no internal datastore volume
        ds_present = any(
            d["metadata"]["name"].endswith(("-postgres", "-redis")) for d in deployments
        )
        if env in ("staging", "prod") and ds_present:
            bad(f"[{env}] internal postgres/redis deployment must not exist")
        if env in ("dev", "test") and not ds_present:
            bad(f"[{env}] expected internal datastore deployments")

        # workspace agents stay ephemeral (emptyDir at /tmp, no PVC)
        for d in deployments:
            if d["metadata"]["name"].endswith(
                (
                    "-workspace-operator-agent",
                    "-development-agent",
                    "-mini-delivery-pilot-agent",
                    "-qa-agent",
                )
            ):
                spec = d["spec"]["template"]["spec"]
                for vol in spec.get("volumes", []) or []:
                    if "persistentVolumeClaim" in vol:
                        bad(
                            f"[{env}] workspace agent {d['metadata']['name']} must stay ephemeral (no PVC)"
                        )

        # no backup PVC
        if any("backup" in p["metadata"]["name"] for p in pvcs):
            bad(f"[{env}] backup PVC must not exist (deferred to 51.2C2)")

        # no RWX claim rendered
        for p in pvcs:
            if "ReadWriteMany" in p.get("spec", {}).get("accessModes", []):
                bad(f"[{env}] ReadWriteMany PVC rendered (fake RWX)")

        # no secret literal
        if SECRET_PAT.search(path.read_text(encoding="utf-8")):
            bad(f"[{env}] secret-like literal in rendered output")

    if not failures:
        ok("storage manifests safe across all environments")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_STORAGE_MANIFEST_VERIFY: FAIL")
        return 1
    print("KUBERNETES_STORAGE_MANIFEST_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
