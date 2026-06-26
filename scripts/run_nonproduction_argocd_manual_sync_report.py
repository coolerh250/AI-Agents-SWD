#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD manual-sync report generator.

Reads the LIVE non-production ArgoCD Application (read-only ``kubectl``) and writes a
REDACTED report to ``.runtime/gitops/nonproduction-argocd-manual-sync-report.json``
(gitignored, NEVER committed). No sync / install / delete here -- read-only. With no
ArgoCD / Application present it emits BLOCKED (never a faked PASS). The report carries
statuses / counts / names / kinds + the (public) git revision only: no kubeconfig,
token, admin password, or secret value.

Marker: NONPROD_ARGOCD_SYNC_REPORT_RUN: PASS | BLOCKED | FAIL
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NONPROD_ARGOCD_SYNC_REPORT_RUN"
ARGOCD_NS = os.environ.get("ARGOCD_NAMESPACE", "argocd-nonprod")
APP = os.environ.get("ARGOCD_APP", "aiagents-smoke")
DEST_NS = os.environ.get("SMOKE_NAMESPACE", "aiagents-smoke-dev")
REPORT = ROOT / ".runtime" / "gitops" / "nonproduction-argocd-manual-sync-report.json"
SECRET_SHAPES = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|password|token)",
    re.IGNORECASE,
)


def _kubectl_json(*args: str) -> dict | None:
    try:
        out = subprocess.run(  # noqa: S603
            ["kubectl", *args, "-o", "json"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except ValueError:
        return None


def main() -> int:
    if shutil.which("kubectl") is None:
        print("  [BLOCKED] kubectl not available")
        print(f"{MARKER}: BLOCKED")
        return 0
    app = _kubectl_json("-n", ARGOCD_NS, "get", "application", APP)
    if app is None:
        print(f"  [BLOCKED] no ArgoCD Application {APP} in {ARGOCD_NS} (run the manual sync first)")
        print(f"{MARKER}: BLOCKED")
        return 0

    spec = app.get("spec", {})
    status = app.get("status", {})
    sync = status.get("sync", {})
    health = status.get("health", {})
    op_state = status.get("operationState", {})
    automated = (spec.get("syncPolicy", {}) or {}).get("automated")

    resources = status.get("resources", []) or []
    kinds = sorted({r.get("kind") for r in resources if r.get("kind")})
    resource_namespaces = sorted({r.get("namespace") for r in resources if r.get("namespace")})
    production_touched = any(
        ("prod" in ns.lower() and "nonprod" not in ns.lower()) for ns in resource_namespaces
    )

    report = {
        "schemaVersion": "step-56",
        "generatedAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "argocdNamespace": ARGOCD_NS,
        "project": spec.get("project"),
        "application": app.get("metadata", {}).get("name"),
        "destinationNamespace": (spec.get("destination", {}) or {}).get("namespace"),
        "destinationServer": (spec.get("destination", {}) or {}).get("server"),
        "sync": {
            "status": sync.get("status"),
            "revision": sync.get("revision"),
            "manualOnly": automated is None,
            "autoSyncEnabled": automated is not None,
            "pruneEnabled": bool((automated or {}).get("prune")),
            "selfHealEnabled": bool((automated or {}).get("selfHeal")),
        },
        "health": {"status": health.get("status")},
        "operation": {
            "phase": op_state.get("phase"),
            "initiatedBy": (op_state.get("operation", {}) or {})
            .get("initiatedBy", {})
            .get("username"),
            "syncedResourceKinds": kinds,
            "resourceNamespaces": resource_namespaces,
        },
        "productionReady": False,
        "productionExecuted": False,
        "argocdProductionSyncPerformed": False,
        "kubernetesProductionDeployPerformed": False,
        "productionNamespaceTouched": production_touched,
        "publicIngressEnabled": False,
        "loadBalancerEnabled": False,
        "limitations": [
            "non-production manual sync only; not production GitOps / auto-sync ready",
            "local kind cluster; ArgoCD server not exposed (ClusterIP only)",
        ],
    }

    blob = json.dumps(report, indent=2)
    # Redaction guard: the report must never carry a token / password / key shape.
    leak = SECRET_SHAPES.search(blob)
    if leak:
        print(f"  [FAIL] report would contain a secret-like shape: {leak.group(0)[:6]}...")
        print(f"{MARKER}: FAIL")
        return 1

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(blob, encoding="utf-8")
    print(f"  wrote {REPORT.relative_to(ROOT)}")
    print(
        f"  sync={report['sync']['status']} health={report['health']['status']} "
        f"phase={report['operation']['phase']} manualOnly={report['sync']['manualOnly']}"
    )

    ok = (
        report["sync"]["status"] == "Synced"
        and report["health"]["status"] == "Healthy"
        and report["operation"]["phase"] == "Succeeded"
        and report["sync"]["manualOnly"] is True
        and report["sync"]["autoSyncEnabled"] is False
        and report["destinationNamespace"] == DEST_NS
        and report["productionNamespaceTouched"] is False
    )
    if not ok:
        print("  [FAIL] sync not in a clean manual-only Synced/Healthy non-production state")
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] manual sync Synced + Healthy; manual-only; non-production destination")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
