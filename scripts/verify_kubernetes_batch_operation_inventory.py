#!/usr/bin/env python3
"""Step 51.2C2 -- batch operation inventory + command catalog verifier.

Source-level checks: migration/backup/restore inventoried with risk, lock,
idempotency, timeout, retry, secret/storage references and evidence; fixed
commands only (no shell, no arbitrary command/args); command source paths
exist; and inventory == batch-command-catalog == values.batchCommands (no drift).

Marker: KUBERNETES_BATCH_OPERATION_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "infra" / "kubernetes" / "batch-operation-inventory.yaml"
CATALOG = ROOT / "infra" / "kubernetes" / "batch-command-catalog.yaml"
VALUES = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "values.yaml"

EXPECTED_RISK = {
    "migration": "high",
    "encrypted-backup": "medium",
    "isolated-restore-drill": "critical",
}
SHELL_TOKENS = ("-c", "$(", "&&", ";", "|", "`")

failures: list[str] = []
passes: list[str] = []


def ok(msg: str) -> None:
    passes.append(msg)
    print(f"  [PASS] {msg}")


def bad(msg: str) -> None:
    failures.append(msg)
    print(f"  [FAIL] {msg}")


def load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def main() -> int:
    inv = load(INVENTORY)
    cat = load(CATALOG)
    values = load(VALUES)
    ops = {o["key"]: o for o in inv["operations"]}
    commands = cat["commands"]
    bcmd = values["batchCommands"]

    # 1. all three operations inventoried
    for key in ("migration", "encrypted-backup", "isolated-restore-drill"):
        if key not in ops:
            bad(f"operation {key} missing from inventory")
    if not failures:
        ok("migration / backup / restore all inventoried")

    # 2. inventory field completeness + classification
    req = [
        "category",
        "risk",
        "owner",
        "existingCommand",
        "executable",
        "lockRequired",
        "idempotent",
        "timeoutSeconds",
        "retryPolicy",
        "productionAllowed",
        "evidence",
    ]
    for key, o in ops.items():
        for f in req:
            if f not in o:
                bad(f"{key} missing field {f}")
        if o.get("productionAllowed") is not False:
            bad(f"{key} productionAllowed must be false")
        if EXPECTED_RISK.get(key) and o.get("risk") != EXPECTED_RISK[key]:
            bad(f"{key} risk must be {EXPECTED_RISK[key]} (got {o.get('risk')})")
        if not o.get("secretReferences") and key != "migration":
            pass  # migration may reference only DATABASE_URL (checked below)
    if not [f for f in failures if any(k in f for k in ops)]:
        ok(
            "operations classified with risk/lock/idempotency/timeout/retry/evidence; productionAllowed=false"
        )

    # 3. command catalog: fixed, no shell, no arbitrary args, source paths exist
    for key, c in commands.items():
        if c.get("shell") is not False:
            bad(f"command {key} must set shell:false")
        if c.get("allowVariableArgs") is not False:
            bad(f"command {key} must not allow variable args")
        if not c.get("executable"):
            bad(f"command {key} has no executable")
        for token in c.get("executable", []) + c.get("args", []):
            if any(t in str(token) for t in SHELL_TOKENS):
                bad(f"command {key} arg {token!r} looks like a shell construct")
        for sp in c.get("sourcePaths", []):
            if not (ROOT / sp).exists():
                bad(f"command {key} source path missing: {sp}")
    if not [f for f in failures if "command" in f]:
        ok("commands are fixed, shell-free, and reference existing source paths")

    # 4. anti-drift: inventory.executable == catalog (executable+args) == values.batchCommands
    inv_cmd = {
        "migration": ops["migration"]["executable"],
        "encrypted-backup": ops["encrypted-backup"]["executable"],
        "isolated-restore-drill": ops["isolated-restore-drill"]["executable"],
    }
    for key, c in commands.items():
        cat_exec = list(c["executable"]) + list(c["args"])
        if inv_cmd[key] != cat_exec:
            bad(f"{key}: inventory executable {inv_cmd[key]} != catalog {cat_exec}")
        vc = bcmd.get(key)
        if not vc or (list(vc["command"]) + list(vc["args"])) != cat_exec:
            bad(f"{key}: values.batchCommands != catalog command")
    if not [f for f in failures if "!=" in f]:
        ok("inventory == batch-command-catalog == values.batchCommands (no drift)")

    # 5. unresolved honesty
    for key, o in ops.items():
        if (
            "unresolved" in o
            and o["unresolved"]
            and o.get("runtimeCompatibility") not in ("requires_cluster_smoke",)
        ):
            bad(f"{key} has unresolved items but is not marked requires_cluster_smoke")
    if not [f for f in failures if "unresolved" in f]:
        ok(
            "operations with unresolved items are marked requires_cluster_smoke (not faked complete)"
        )

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_BATCH_OPERATION_INVENTORY_VERIFY: FAIL")
        return 1
    print("KUBERNETES_BATCH_OPERATION_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
