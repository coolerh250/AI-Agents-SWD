"""Step 61 -- backup / restore / DR: no production action anywhere.

Source-level guard across the SDK + API + scripts: no real restore / failover / cleanup
execution / cluster teardown / ArgoCD sync / external upload path, and no committed raw
dump / secret / kubeconfig literal. (Field NAMES that assert an action did NOT happen --
e.g. ``argocd_sync_performed`` / ``production_executed`` -- are allowed.)
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "shared" / "sdk" / "backup_restore_dr"
API = ROOT / "apps" / "orchestrator" / "src" / "backup_restore_dr_api.py"
SCRIPTS = [
    ROOT / "scripts" / "generate_backup_dr_runtime_inventory.py",
    ROOT / "scripts" / "generate_controlled_cleanup_review.py",
    ROOT / "scripts" / "run_nonproduction_restore_validation.py",
]

# Real execution primitives that must never appear.
FORBIDDEN_EXEC = (
    "subprocess",
    "os.system",
    "shutil.rmtree",
    "os.remove",
    "os.unlink",
    "kubectl ",
    "docker push",
    "argocd app sync",
    "boto3",
    "google.cloud",
)


def _sources() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for f in SDK.glob("*.py"):
        out.append((f.name, f.read_text(encoding="utf-8")))
    out.append((API.name, API.read_text(encoding="utf-8")))
    for s in SCRIPTS:
        out.append((s.name, s.read_text(encoding="utf-8")))
    return out


def test_no_real_execution_primitives() -> None:
    for name, src in _sources():
        for forbidden in FORBIDDEN_EXEC:
            # The cleanup-review generator legitimately imports shutil for disk_usage only.
            if forbidden == "shutil.rmtree" and "shutil.disk_usage" in src:
                pass
            assert forbidden not in src, f"{forbidden} in {name}"


def test_no_secret_shaped_literals() -> None:
    import re

    shapes = re.compile(
        r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|"
        r"AKIA[0-9A-Z]{16})"
    )
    for name, src in _sources():
        assert not shapes.search(src), f"secret-shaped literal in {name}"
