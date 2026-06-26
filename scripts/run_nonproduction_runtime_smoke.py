#!/usr/bin/env python3
"""Step 55.1 -- REAL non-production Kubernetes runtime smoke (report generator).

Runs against a SAFE non-production cluster (kind ``aiagents-smoke`` by default)
where the scoped ai-agents-platform release is already installed (see
docs/operations/nonproduction-cluster-bootstrap-plan.md). It performs REAL
``kubectl`` queries + an in-cluster connectivity probe and writes a REDACTED
runtime smoke report to ``.runtime/kubernetes/nonproduction-runtime-smoke-report.json``
(gitignored, NEVER committed). The verifiers consume that report so a PASS
reflects the live cluster, not mere cluster presence.

No deploy / install / sync here -- read-only against an already-deployed release.
With no safe cluster it emits BLOCKED_NO_SAFE_CLUSTER (never a faked PASS). The
report carries statuses / counts / names only: no kubeconfig, token, cert,
secret, or rendered manifest.

Marker: NONPROD_RUNTIME_SMOKE_RUN: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lib.nonprod_cluster_detect import detect_cluster  # noqa: E402

MARKER = "NONPROD_RUNTIME_SMOKE_RUN"
NS = os.environ.get("SMOKE_NAMESPACE", "aiagents-smoke-dev")
RELEASE = os.environ.get("SMOKE_RELEASE", "aiagents-smoke")
# Chart resources are prefixed with the chart fullname (NOT the helm release name).
PREFIX = os.environ.get("SMOKE_FULLNAME", "ai-agents-platform")
REPORT = ROOT / ".runtime" / "kubernetes" / "nonproduction-runtime-smoke-report.json"

# Candidate internal connectivity edges (only those whose target is deployed run).
CONNECTIVITY_EDGES = [
    ("orchestrator", "policy-engine", 8001),
    ("orchestrator", "approval-engine", 8002),
    ("orchestrator", "audit-service", 8003),
]


def _kubectl_json(*args: str) -> dict:
    out = subprocess.run(  # noqa: S603
        ["kubectl", "-n", NS, *args, "-o", "json"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
    )
    if out.returncode != 0:
        return {}
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {}


def _section_pods() -> dict:
    pods = _kubectl_json("get", "pods").get("items", [])
    not_ready: list[str] = []
    bad_states: list[str] = []
    ready = 0
    completed = 0
    for p in pods:
        name = p["metadata"]["name"]
        phase = p["status"].get("phase")
        statuses = p["status"].get("containerStatuses", []) or []
        if phase == "Succeeded":
            completed += 1
            continue
        all_ready = bool(statuses) and all(c.get("ready") for c in statuses)
        for c in statuses:
            waiting = (c.get("state", {}) or {}).get("waiting", {}) or {}
            reason = waiting.get("reason", "")
            if reason in (
                "CrashLoopBackOff",
                "ImagePullBackOff",
                "ErrImagePull",
                "CreateContainerConfigError",
            ):
                bad_states.append(f"{name}:{reason}")
        if all_ready:
            ready += 1
        else:
            not_ready.append(name)
    running_expected = len(pods) - completed
    status = "pass" if (not not_ready and not bad_states and running_expected > 0) else "fail"
    return {
        "status": status,
        "runningExpected": running_expected,
        "ready": ready,
        "completedJobPods": completed,
        "notReady": not_ready,
        "badStates": bad_states,
    }


def _section_services() -> dict:
    svcs = _kubectl_json("get", "services").get("items", [])
    eps = {e["metadata"]["name"]: e for e in _kubectl_json("get", "endpoints").get("items", [])}
    names: list[str] = []
    without_ep: list[str] = []
    for s in svcs:
        n = s["metadata"]["name"]
        names.append(n)
        subsets = (eps.get(n, {}) or {}).get("subsets") or []
        addrs = [a for ss in subsets for a in (ss.get("addresses") or [])]
        if not addrs:
            without_ep.append(n)
    status = "pass" if (names and not without_ep) else "fail"
    return {
        "status": status,
        "services": len(names),
        "withEndpoints": len(names) - len(without_ep),
        "withoutEndpoints": without_ep,
    }


def _exec_probe(from_app: str, target: str, port: int) -> dict:
    cmd = (
        "import urllib.request,sys\n"
        f"r=urllib.request.urlopen('http://{target}:{port}/health',timeout=5)\n"
        "print(r.status)"
    )
    out = subprocess.run(  # noqa: S603
        [
            "kubectl",
            "-n",
            NS,
            "exec",  # noqa: S607
            f"deploy/{PREFIX}-{from_app}",
            "--",
            "python",
            "-c",
            cmd,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    code = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    ok = out.returncode == 0 and code == "200"
    return {"from": from_app, "to": f"{target}:{port}/health", "ok": ok, "code": code or "none"}


def _deployed(deploy_names: set[str], app: str) -> bool:
    return f"{PREFIX}-{app}" in deploy_names


def _section_connectivity(deploy_names: set[str]) -> dict:
    checks: list[dict] = []
    for src, dst, port in CONNECTIVITY_EDGES:
        if _deployed(deploy_names, src) and _deployed(deploy_names, dst):
            checks.append(_exec_probe(src, dst, port))
    status = "pass" if (checks and all(c["ok"] for c in checks)) else "fail"
    return {"status": status, "checks": checks}


def _section_networkpolicy() -> dict:
    pols = _kubectl_json("get", "networkpolicies").get("items", [])
    names = [p["metadata"]["name"] for p in pols]
    has_deny_ingress = any(n.endswith("default-deny-ingress") for n in names)
    has_deny_egress = any(n.endswith("default-deny-egress") for n in names)
    has_dns = any("allow-dns" in n for n in names)
    # kindnet (the kind default CNI) does NOT enforce NetworkPolicy. The policies
    # are rendered + applied correctly, but runtime enforcement is not observable
    # here. Reported honestly; never claimed as enforced.
    status = "pass" if (pols and has_deny_ingress and has_deny_egress and has_dns) else "fail"
    return {
        "status": status,
        "policies": len(pols),
        "defaultDenyIngress": has_deny_ingress,
        "defaultDenyEgress": has_deny_egress,
        "dnsAllow": has_dns,
        "enforcementObserved": False,
        "enforcementLimitation": "kindnet_does_not_enforce_networkpolicy",
    }


def _section_pvc() -> dict:
    pvcs = _kubectl_json("get", "pvc").get("items", [])
    claims = []
    unbound = []
    for c in pvcs:
        n = c["metadata"]["name"]
        phase = c["status"].get("phase")
        size = (c["status"].get("capacity", {}) or {}).get("storage", "")
        claims.append({"name": n, "bound": phase == "Bound", "size": size})
        if phase != "Bound":
            unbound.append(n)
    status = "pass" if (claims and not unbound) else "fail"
    return {"status": status, "claims": claims, "unbound": unbound}


def _section_security() -> dict:
    pods = _kubectl_json("get", "pods").get("items", [])
    checked = 0
    violations: list[str] = []
    read_only_app = 0
    for p in pods:
        if p["status"].get("phase") == "Succeeded":
            continue
        name = p["metadata"]["name"]
        psc = p["spec"].get("securityContext", {}) or {}
        c0 = (p["spec"].get("containers") or [{}])[0]
        csc = c0.get("securityContext", {}) or {}
        checked += 1
        run_as_user = psc.get("runAsUser", csc.get("runAsUser"))
        if psc.get("runAsNonRoot") is not True:
            violations.append(f"{name}:runAsNonRoot!=true")
        if run_as_user in (0, None):
            violations.append(f"{name}:runAsUser={run_as_user}")
        drop = (csc.get("capabilities", {}) or {}).get("drop", []) or []
        if "ALL" not in drop:
            violations.append(f"{name}:caps_not_drop_all")
        if csc.get("allowPrivilegeEscalation") is not False:
            violations.append(f"{name}:privesc_not_false")
        if csc.get("readOnlyRootFilesystem") is True:
            read_only_app += 1
    status = "pass" if (checked > 0 and not violations) else "fail"
    return {
        "status": status,
        "podsChecked": checked,
        "readOnlyRootFsCount": read_only_app,
        "violations": violations,
    }


def _section_batch() -> dict:
    jobs = _kubectl_json("get", "jobs").get("items", [])
    migration = None
    for j in jobs:
        if j["metadata"]["name"].endswith("-migration"):
            succeeded = (j["status"].get("succeeded") or 0) >= 1
            migration = {"completed": succeeded, "executionEnabled": False}
    status = "pass" if (migration and migration["completed"]) else "fail"
    return {"status": status, "migration": migration or {"completed": False}}


def main() -> int:
    available, safe, reason = detect_cluster()
    if not (available and safe):
        print(f"  [BLOCKED] runtime smoke requires a safe non-production cluster ({reason})")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0

    deploys = _kubectl_json("get", "deployments").get("items", [])
    deploy_names = {d["metadata"]["name"] for d in deploys}
    if not deploy_names:
        print(f"  [BLOCKED] no deployed release in {NS} (run the bootstrap + helm smoke first)")
        print(f"{MARKER}: BLOCKED_NO_SAFE_CLUSTER")
        return 0

    sections = {
        "podStatus": _section_pods(),
        "serviceHealth": _section_services(),
        "connectivity": _section_connectivity(deploy_names),
        "networkPolicy": _section_networkpolicy(),
        "pvc": _section_pvc(),
        "securityContext": _section_security(),
        "batchJobs": _section_batch(),
    }
    deployed = sorted(n[len(PREFIX) + 1 :] for n in deploy_names)
    failed = [k for k, v in sections.items() if v["status"] != "pass"]
    report = {
        "schemaVersion": "step-55.1",
        "generatedAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cluster": {"type": "kind", "contextSafe": True, "nonProduction": True},
        "namespace": NS,
        "release": RELEASE,
        "scope": {
            "deployedComponents": deployed,
            "rationale": "host-capacity-scoped non-production control-plane smoke",
        },
        "productionReady": False,
        "productionExecuted": False,
        "kubernetesProductionDeployPerformed": False,
        "argocdSyncPerformed": False,
        "sections": sections,
        "overall": "pass" if not failed else "fail",
        "failedSections": failed,
        "limitations": [
            "scoped subset of platform components (non-production host capacity)",
            "kindnet does not enforce NetworkPolicy (policies rendered, not enforced)",
            "chart migration execution is fail-closed (no DB schema applied)",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  wrote {REPORT.relative_to(ROOT)}")
    for k, v in sections.items():
        print(f"  {k}: {v['status']}")
    if failed:
        print(f"  [FAIL] sections failed: {failed}")
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] all runtime smoke sections passed against the live non-production cluster")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
