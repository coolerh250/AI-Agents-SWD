#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-2 -- identity and secret provisioning decision-package self-verifier.

Deterministic, offline checks over the RA-2 deliverables plus negative proof that this stage
introduced no runtime identity/secret implementation, no deployment configuration change, and no
activation. Reads only committed repository content -- it never reads a real secret, never contacts
an IdP, Vault, Kubernetes, or any cloud API, and never starts a runtime container.

Marker: STEP66C4_BE3_RA2_IDENTITY_SECRET_DECISION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
import pathlib

# AT-M2 remediation: this stage's rejection window ends where an authorized successor
# milestone takes over. Without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from successor_lifecycle import successor_window_end  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
SECURITY = ROOT / "docs" / "security"

PACKAGE = CONTRACT / "be3-ra2-identity-secret-provisioning-decision-package.md"
INVENTORY = SECURITY / "be3-ra2-current-state-identity-secret-inventory.md"
THREAT = SECURITY / "be3-ra2-identity-secret-threat-and-trust-analysis.md"
DECOMP = HANDOFF / "be3-ra2-implementation-stage-decomposition.md"
EVIDENCE = ROOT / "docs" / "test" / "step66c4-be3-ra2-identity-secret-decision-evidence.md"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"

BASELINE_MAIN = "c1db4cc"
DECISION_IDS = tuple(f"RA2-D{n:02d}" for n in range(1, 13))
RA_P_CLASSIFICATIONS = (
    "RESOLVED_BY_RA2_PO_DECISION",
    "REQUIRES_RA2_PO_DECISION",
    "DEFERRED_TO_RA6",
    "DEFERRED_TO_RA7",
    "DEFERRED_TO_RA9_RA11",
)

MARKER = "STEP66C4_BE3_RA2_IDENTITY_SECRET_DECISION_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (PACKAGE, INVENTORY, THREAT, DECOMP, EVIDENCE, RESUME_MODEL, REPLAY_MODEL):
        if not p.is_file():
            bad(f"missing required file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    package = PACKAGE.read_text(encoding="utf-8")
    inventory = INVENTORY.read_text(encoding="utf-8")
    threat = THREAT.read_text(encoding="utf-8")
    decomp = DECOMP.read_text(encoding="utf-8")
    resume_src = RESUME_MODEL.read_text(encoding="utf-8")
    replay_src = REPLAY_MODEL.read_text(encoding="utf-8")
    progress_md = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")

    # 1. Baseline main is the authorized commit.
    rc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASELINE_MAIN, "HEAD"], cwd=ROOT, capture_output=True
    ).returncode
    if rc != 0:
        bad(f"check1: baseline main {BASELINE_MAIN} is not an ancestor of HEAD")
    if BASELINE_MAIN not in package:
        bad(f"check1b: decision package does not record baseline main {BASELINE_MAIN}")

    # 2. Operator identity inventory is complete (all four mandatory questions answered).
    for probe in (
        "正式 operator authenticator",
        "request payload/header",
        "Admin Console session",
        "可驗證的人類 operator identity",
    ):
        if probe not in inventory:
            bad(f"check2: operator identity inventory missing mandatory question: {probe}")
    if "X-Task-Actor" not in inventory or "X-Task-Role" not in inventory:
        bad("check2b: inventory does not cite the header-based operator identity call sites")

    # 3. Service Identity production vs test call sites are explicitly distinguished.
    if not re.search(r"tests/\s+16 call sites", inventory):
        bad("check3: inventory does not record the test-only Service Identity call-site count")
    if not re.search(r"apps/\s+0 call sites", inventory) or not re.search(
        r"shared/\s+0 call sites", inventory
    ):
        bad("check3b: inventory does not record ZERO production Service Identity call sites")
    if "NO REAL SERVICE IDENTITY AUTHENTICATOR EXISTS" not in inventory:
        bad("check3c: inventory does not state the required no-authenticator conclusion")

    # 4. Policy Authority authentication and secret loading are inventoried.
    for probe in ("compare_digest", "BE3_RESUME_POLICY_AUTHORITY", "os.environ"):
        if probe not in inventory:
            bad(f"check4: Policy Authority inventory missing evidence probe: {probe}")
    if "dual-key rotation" not in inventory.lower():
        bad("check4b: Policy Authority rotation support not inventoried")

    # 5. Secret backend inventory uses the required classification vocabulary.
    for cls in (
        "IMPLEMENTED_AND_ACTIVE",
        "IMPLEMENTED_NOT_ACTIVE",
        "TEMPLATE_ONLY",
        "DEV_ONLY",
        "REFERENCED_NOT_IMPLEMENTED",
        "ABSENT",
    ):
        if cls not in inventory:
            bad(f"check5: secret backend inventory missing classification: {cls}")
    if "server -dev" not in inventory:
        bad("check5b: inventory does not distinguish Vault dev mode from production-grade Vault")

    # 6. At least 12 identity/secret decisions exist.
    present = [d for d in DECISION_IDS if f"Decision ID:          {d}" in package]
    if len(present) < 12:
        bad(f"check6: only {len(present)} decisions found; at least 12 required")

    # 7. Every decision has multiple options and a PO-required status.
    po_required = package.count("Status: PRODUCT_OWNER_DECISION_REQUIRED")
    if po_required < 12:
        bad(f"check7: only {po_required} decisions marked PRODUCT_OWNER_DECISION_REQUIRED")
    for d in present:
        block = package.split(f"Decision ID:          {d}", 1)[-1].split("Decision ID:", 1)[0]
        if "Option A:" not in block or "Option B:" not in block:
            bad(f"check7b: {d} does not present at least two options")
        if "Product Owner selection:   PENDING" not in block:
            bad(f"check7c: {d} does not leave Product Owner selection PENDING")

    # 8. Nothing is marked selected / approved / binding / canonical.
    forbidden = re.compile(
        r"(Status:\s*(SELECTED|APPROVED|BINDING|CANONICAL))"
        r"|(Product Owner selection:\s*Option)"
        r"|(canonical backend)|(official IdP)|(final decision)",
        re.IGNORECASE,
    )
    hit = forbidden.search(package)
    if hit:
        bad(f"check8: decision package contains a selected/approved marker: {hit.group(0)!r}")
    if "Decided by Claude Code: 0" not in package:
        bad("check8b: decision package does not assert zero decisions made by Claude Code")

    # 9. All 11 RA-P open decisions are carried forward and classified.
    if "carried forward: 11" not in package or "dropped: 0" not in package:
        bad("check9: RA-P carry-forward integrity statement missing or incomplete")
    for cls in RA_P_CLASSIFICATIONS:
        if cls not in package:
            bad(f"check9b: RA-P carry-forward missing classification: {cls}")
    for n in range(1, 12):
        if f"RA-P {n}." not in package:
            bad(f"check9c: RA-P open decision {n} not carried forward")

    # 10. Threat model covers the required threat classes.
    for probe in ("impersonation", "replay", "revocation", "leakage"):
        if probe not in threat.lower():
            bad(f"check10: threat model does not cover: {probe}")
    if "Zero Trust" not in threat or "NOT achieved" not in threat:
        bad("check10b: threat model does not explicitly disclaim Zero Trust completion")

    # 11. Implementation stages carry dependencies and review classification.
    for stage in ("RA-2I1", "RA-2I2", "RA-2I3", "RA-2I4", "RA-2I5", "RA-2I6", "RA-2R"):
        if stage not in decomp:
            bad(f"check11: implementation decomposition missing stage {stage}")
    if "Required PO decisions:" not in decomp or "Independent review:" not in decomp:
        bad("check11b: stage records missing dependency or review-requirement fields")
    if "Earliest executable" not in decomp:
        bad("check11c: decomposition does not identify the earliest executable stage")

    # 12. No real secret was read or output -- no secret-shaped literal in this stage's docs.
    secret_shaped = re.compile(
        r"(BEGIN [A-Z ]*PRIVATE KEY)"
        r"|(password\s*[:=]\s*['\"][^'\"]{3,})"
        r"|(postgres(?:ql)?://[^\s`]*:[^\s`@]+@)",
        re.IGNORECASE,
    )
    for name, text in (
        ("package", package),
        ("inventory", inventory),
        ("threat", threat),
        ("decomposition", decomp),
    ):
        m = secret_shaped.search(text)
        if m:
            bad(f"check12: {name} contains secret-shaped content: {m.group(0)[:40]!r}")

    # 13/14. No runtime authentication/secret code and no infra credential change in this stage.
    changed = _git("diff", "--name-only", BASELINE_MAIN, successor_window_end(BASELINE_MAIN))
    changed_files = [f.strip() for f in changed.splitlines() if f.strip()]
    for f in changed_files:
        if f.startswith("apps/") or f.startswith("shared/"):
            bad(f"check13: this stage changed runtime code: {f}")
        if f.startswith("infra/") or f.startswith("migrations/"):
            bad(f"check14: this stage changed infra/migration configuration: {f}")

    # 15. No shared migration / deployment / activation recorded.
    for probe in ("NO DEPLOYMENT", "NO ACTIVATION"):
        if probe not in decomp:
            bad(f"check15: decomposition does not record {probe}")

    # 16. Four BE3 feature gates remain default false.
    for var, src, label in (
        ("BE3_RESUME_API_ENABLED", resume_src, "resume_request_model.py"),
        ("BE3_RESUME_COMMAND_ENABLED", resume_src, "resume_request_model.py"),
        ("BE3_REPLAY_API_ENABLED", replay_src, "replay_request_model.py"),
        ("BE3_REPLAY_EXECUTION_ENABLED", replay_src, "replay_request_model.py"),
    ):
        if f'os.environ.get("{var}", "false")' not in src:
            bad(f"check16: {var} default is not 'false' in {label}")

    # 17. No worker/relay/consumer or runtime action.
    if "no poller/relay/worker/consumer" not in decomp.lower() and (
        "start a\n  poller/relay/worker/consumer" not in decomp
        and "poller/relay/worker/consumer" not in decomp
    ):
        bad("check17: decomposition does not prohibit worker/relay/consumer startup")

    # 18. RA-3 and implementation stages are not authorized.
    if "NOT AUTHORIZED" not in decomp or "Authorized stages: 0" not in decomp:
        bad("check18: decomposition does not record that no stage is authorized")

    # 19. production_executed_true_count = 0.
    if "production_executed_true_count: 0" not in progress_md:
        bad("check19: production_executed_true_count: 0 not recorded in source/progress.md")
    if "production_executed_true_count: 0" not in package:
        bad("check19b: production_executed_true_count: 0 not recorded in the decision package")

    # 20. The Product Owner decision package is the next gate.
    if "Next authorization required" not in decomp:
        bad("check20: decomposition does not state the next required authorization")
    if "PRODUCT OWNER DECISIONS PENDING" not in decomp:
        bad("check20b: decomposition does not record Product Owner decisions as the pending gate")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Baseline recorded; operator/Service-Identity/Policy-Authority/secret-backend")
    print("       inventories complete with production-vs-test separation; 12 decisions present,")
    print(
        "       each with multiple options, PENDING selection, and PRODUCT_OWNER_DECISION_REQUIRED;"
    )
    print(
        "       nothing marked selected/approved/binding/canonical; all 11 RA-P open items carried"
    )
    print(
        "       forward and classified; threat model covers impersonation/replay/revocation/leakage"
    )
    print("       and disclaims Zero Trust; implementation stages carry dependencies and review")
    print("       classification; no secret-shaped content; no runtime, infra, or migration file")
    print("       changed by this stage; four BE3 gates remain default false; no stage authorized;")
    print("       production_executed_true_count is 0.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
