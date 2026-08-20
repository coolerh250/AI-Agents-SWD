#!/usr/bin/env python3
"""Step 66D-DESIGN-M1 -- canonical merge verifier for the Unified Control Center design package.

Deterministic and read-only. Confirms PR #26 was merged as a non-squash two-parent merge with the
three design commits preserved, that the design positive scope is frozen to the immutable
9c5210d...bb8eab7 range rather than to current HEAD, that the current-state rejection guard is
still HEAD-relative, and that every canonical design contract carried into main is intact.

Starts no runtime, container, database or external provider.

Marker: STEP66D_DESIGN_M1_CANONICAL_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

# AT-M2 remediation: cross-stage meta-guards require a stage's runtime denylist to keep
# scanning current state. The shared call below IS current state unless a successor
# milestone is canonically authorized: the property is unchanged, only the spelling is shared.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import scans_current_state  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def scans_current_state(body: str, anchor: str) -> bool:
        """Strictest fallback: only the literal current-state spellings are accepted."""
        return any(
            form in body for form in (f'"--name-only", {anchor}, "HEAD"', f'f"{{{anchor}}}...HEAD"')
        )


ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "STEP66D_DESIGN_M1_CANONICAL_MERGE_VERIFY"

PRE_MERGE_MAIN = "9c5210d190b82b76575ba8d456b5d2005c2867d2"
ORIGINAL_DESIGN_COMMIT = "47dcbe9feda6633e3d0835d16dcaa0866a26c2cf"
RM1_COMMIT = "c9ee13b7389f0b4977cab835337c828675a4a67d"
DESIGN_STAGE_HEAD = "bb8eab70ee7fb252329fe05c4b7039c2ed0f694b"
MERGE_COMMIT = "e4efb88bad01f72ccc73bdd0d13ff9b8e29fbda2"

DESIGN_DIR = "docs/design/66d-delivery-acceptance"
HANDOFF_DIR = "docs/handoffs/66d-delivery-acceptance"

DESIGN_VERIFIER = ROOT / "scripts/verify_step66d_design_unified_control_center.py"
DESIGN_TESTS = ROOT / "tests/test_step66d_design_unified_control_center.py"
MANIFEST = ROOT / DESIGN_DIR / "step66d-design-contract-manifest.json"
YAML_MANIFEST = ROOT / DESIGN_DIR / "step66d-design-contract-manifest.yaml"
ROUTES_DOC = ROOT / DESIGN_DIR / "step66d-design-route-and-drilldown-map.md"
MATRIX = ROOT / DESIGN_DIR / "step66d-design-state-error-permission-matrix.md"
RECORD = ROOT / HANDOFF_DIR / "step66d-design-m1-canonical-merge-record.md"
GAPS = ROOT / HANDOFF_DIR / "step66d-design-gap-and-dependency-register.md"
APP_TSX = ROOT / "apps/admin-console/src/App.tsx"

DESIGN_EXPECTED_PATHS = frozenset(
    {
        f"{DESIGN_DIR}/step66d-design-unified-control-center-ia.md",
        f"{DESIGN_DIR}/step66d-design-route-and-drilldown-map.md",
        f"{DESIGN_DIR}/step66d-design-delivery-inbox-spec.md",
        f"{DESIGN_DIR}/step66d-design-delivery-review-interactions.md",
        f"{DESIGN_DIR}/step66d-design-state-error-permission-matrix.md",
        f"{DESIGN_DIR}/step66d-design-wireframes.md",
        f"{DESIGN_DIR}/step66d-design-accessibility-responsive-spec.md",
        f"{DESIGN_DIR}/step66d-design-frontend-handoff.md",
        f"{DESIGN_DIR}/step66d-design-contract-manifest.json",
        f"{HANDOFF_DIR}/step66d-design-existing-ui-route-inventory.md",
        f"{HANDOFF_DIR}/step66d-design-gap-and-dependency-register.md",
        f"{HANDOFF_DIR}/step66d-design-evidence.md",
        "scripts/verify_step66d_design_unified_control_center.py",
        "tests/test_step66d_design_unified_control_center.py",
    }
)

REVIEW_ACTIONS = ["ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"]
PO_DECISIONS = ["ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED"]
STATUSES = [
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "CHANGES_REQUESTED",
    "QA_RERUN_REQUESTED",
    "ACCEPTED",
    "REJECTED",
    "ARCHIVED",
    "EXPIRED",
]
FORBIDDEN_PREFIXES = (
    "apps/",
    "agents/",
    "services/",
    "shared/",
    "migrations/",
    "infra/",
    "helm/",
    "k8s/",
    ".github/workflows/",
)

failures: list[str] = []
checks_run = 0


def expect(ok: bool, label: str, message: str) -> None:
    global checks_run
    checks_run += 1
    if not ok:
        failures.append(f"{label}: {message}")
        print(f"  [FAIL] {label}: {message}")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def is_ancestor(commit: str, ref: str = "HEAD") -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, ref],
            cwd=ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def manifest() -> dict:
    try:
        return json.loads(read(MANIFEST))
    except json.JSONDecodeError:
        return {}


def source_route_classes() -> dict[str, str]:
    classes: dict[str, str] = {}
    for block in re.split(r"(?=<Route\s)", read(APP_TSX)):
        match = re.match(r'<Route\s+path="([^"]+)"', block)
        if not match:
            continue
        segment = block.split("/>")[0] if "/>" in block else block[:400]
        classes[match.group(1)] = "PLACEHOLDER" if "PlaceholderPage" in segment else "REAL_PAGE"
    return classes


def normalise(text: str) -> str:
    upper = (text or "").upper()
    if "PLACEHOLDER" in upper:
        return "PLACEHOLDER"
    if "PLANNED" in upper or "ABSENT" in upper:
        return "ABSENT"
    return "REAL_PAGE" if upper else ""


def main() -> int:
    data = manifest()
    verifier_src = read(DESIGN_VERIFIER)
    tests_src = read(DESIGN_TESTS)
    record = read(RECORD)

    # 1-3. commit identities and PR shape
    expect(is_ancestor(PRE_MERGE_MAIN), "check01", "pre-merge main is not an ancestor of HEAD")
    expect(is_ancestor(DESIGN_STAGE_HEAD), "check02", "PR head bb8eab7 is not an ancestor of HEAD")
    expect(
        git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{DESIGN_STAGE_HEAD}") == "3",
        "check03",
        "the PR does not contain exactly 3 commits",
    )

    # 4. all three design commits preserved
    for label, commit in (
        ("47dcbe9", ORIGINAL_DESIGN_COMMIT),
        ("c9ee13b", RM1_COMMIT),
        ("bb8eab7", DESIGN_STAGE_HEAD),
    ):
        expect(is_ancestor(commit), "check04", f"design commit {label} is not preserved in main")

    # 5-6. non-squash two-parent merge with the correct parents
    parents = git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    expect(len(parents) == 2, "check05", f"merge commit is not a two-parent merge: {parents}")
    expect(
        parents[:2] == [PRE_MERGE_MAIN, DESIGN_STAGE_HEAD],
        "check06",
        f"merge parents are {parents}, expected [{PRE_MERGE_MAIN}, {DESIGN_STAGE_HEAD}]",
    )
    expect(is_ancestor(MERGE_COMMIT), "check06b", "the merge commit is not an ancestor of HEAD")

    # 7-8. canonical IA and principle
    expect(
        data.get("canonical_ia") == "UNIFIED_CONTROL_CENTER",
        "check07",
        f"canonical_ia is {data.get('canonical_ia')!r}",
    )
    expect(
        data.get("implementation_principle") == "UNIFIED_OVERVIEW_WITH_EXISTING_ROUTE_DRILL_DOWN",
        "check08",
        f"implementation_principle is {data.get('implementation_principle')!r}",
    )

    # 9-11. frozen positive scope, exact 14 paths, no HEAD positive endpoint
    expect(
        f'DESIGN_STAGE_HEAD = "{DESIGN_STAGE_HEAD}"' in verifier_src
        and 'DESIGN_POSITIVE_RANGE = f"{DESIGN_BASELINE}...{DESIGN_STAGE_HEAD}"' in verifier_src,
        "check09",
        "the design verifier does not freeze its positive scope to 9c5210d...bb8eab7",
    )
    changed = {
        line.strip().replace("\\", "/")
        for line in git(
            "diff", "--name-only", f"{PRE_MERGE_MAIN}...{DESIGN_STAGE_HEAD}"
        ).splitlines()
        if line.strip()
    }
    expect(
        changed == DESIGN_EXPECTED_PATHS,
        "check10",
        f"frozen range != registry; missing={sorted(DESIGN_EXPECTED_PATHS - changed)} "
        f"unexpected={sorted(changed - DESIGN_EXPECTED_PATHS)}",
    )
    expect(
        'f"{DESIGN_BASELINE}...HEAD"' not in verifier_src,
        "check11",
        "the design verifier still uses current HEAD as a positive scope endpoint",
    )

    # 12. rejection guard remains current-state
    expect(
        "RUNTIME_GUARD_ANCHOR" in verifier_src
        and scans_current_state(verifier_src, "RUNTIME_GUARD_ANCHOR")
        and "def current_state_paths(" in verifier_src,
        "check12",
        "the current-state rejection guard no longer scans current HEAD",
    )

    # 13-14. manifest format
    expect(MANIFEST.is_file() and bool(data), "check13", "the JSON design manifest is missing")
    expect(not YAML_MANIFEST.exists(), "check14", "the superseded YAML manifest is present again")

    # 15. route truthfulness across four representations
    source = source_route_classes()
    inventory = {
        r["path"]: normalise(r.get("classification", ""))
        for r in data.get("route_inventory", {}).get("routes", [])
    }
    planned = {
        r["path"]: normalise(r.get("classification", ""))
        for r in data.get("route_inventory", {}).get("planned_absent_routes", [])
    }
    semantic = {
        r["route"]: normalise(r.get("current_state", ""))
        for r in data.get("semantic_routes", [])
        if r.get("route")
    }
    mismatched = [p for p, cls in source.items() if inventory.get(p, cls) != cls]
    expect(not mismatched, "check15", f"route_inventory disagrees with App.tsx for {mismatched}")
    for path in (
        "/projects/:projectId/control-center",
        "/delivery-submissions/:deliverySubmissionId/review",
    ):
        expect(path not in source, "check15b", f"{path} is declared absent but exists in App.tsx")
        expect(
            planned.get(path) == "ABSENT" and semantic.get(path) == "ABSENT",
            "check15c",
            f"{path} is not recorded as absent/planned in every representation",
        )
    for path in ("/delivery-inbox", "/delivery-detail"):
        expect(
            source.get(path) == "PLACEHOLDER"
            and inventory.get(path) == "PLACEHOLDER"
            and semantic.get(path) == "PLACEHOLDER",
            "check15d",
            f"{path} is not PLACEHOLDER in every representation",
        )
    for path in ("/dlq-retry", "/approvals"):
        expect(
            source.get(path) == "PLACEHOLDER" and inventory.get(path) == "PLACEHOLDER",
            "check15e",
            f"{path} is not PLACEHOLDER in source and inventory",
        )

    # 16-18. exact enum sets
    expect(
        data.get("review_gate_actions") == REVIEW_ACTIONS, "check16", "review actions != exact 6"
    )
    expect(
        data.get("product_owner_decisions") == PO_DECISIONS, "check17", "PO decisions != exact 3"
    )
    expect(
        sorted(data.get("canonical_statuses", [])) == sorted(STATUSES),
        "check18",
        "canonical statuses != exact 9",
    )

    # 19-21. derived counts
    expect(len(data.get("open_gaps", [])) == 16, "check19", "manifest gap count != 16")
    expect(
        len(re.findall(r"^### (DG-\d+)", read(GAPS), re.M)) == 16,
        "check19b",
        "gap register does not contain 16 DG headings",
    )
    expect(
        len(data.get("frontend_inventory", {}).get("mutation_surfaces", [])) == 5,
        "check20",
        "mutation surfaces != exact 5",
    )
    timeline = [
        line
        for line in read(MATRIX).splitlines()
        if line.lower().strip().startswith("| activity timeline")
    ]
    cells = [c.strip() for c in timeline[0].strip().strip("|").split("|")] if timeline else []
    expect(
        len(cells) == 8 and all(cells),
        "check21",
        "the Activity Timeline row does not define all 7 data states",
    )

    # 22. OperatorConsole coexistence
    overlap = data.get("operator_console_overlap", {})
    expect(
        overlap.get("existing_route") == "/operator"
        and "Delivery Review" in str(overlap.get("canonical_po_decision_entry_point", ""))
        and bool(overlap.get("fe2_coexistence_gate")),
        "check22",
        "the OperatorConsole coexistence contract is missing or incomplete",
    )

    # 23. R2-F01..F03 recorded closed
    for finding in ("R2-F01", "R2-F02", "R2-F03"):
        expect(
            re.search(rf"{finding}[^\n]*", record) is not None and "CLOSED" in record,
            "check23",
            f"{finding} is not recorded as closed in the merge record",
        )

    # 24-25. advisories tracked but not remediated
    # The advisory must be present, tracked, unremediated, and described by its ACTUAL mechanism
    # (subprocess.run without encoding=). Any mention of read_text must appear only in a negating
    # sentence, never as the asserted cause.
    adv = ""
    if "ADV-UTF8-01" in record:
        adv = record.split("ADV-UTF8-01", 1)[1].split("ADV-SUITE-01")[0]
    read_text_claims = [
        sentence
        for sentence in re.split(r"(?<=\.)\s+", adv)
        if "read_text" in sentence and not re.search(r"\bNOT\b|\bnever\b", sentence)
    ]
    expect(
        bool(adv)
        and "NOT REMEDIATED" in adv
        and "subprocess.run" in adv
        and "encoding=" in adv
        and not read_text_claims,
        "check24",
        "ADV-UTF8-01 is not recorded accurately as tracked, unremediated and caused by "
        f"subprocess.run without encoding= (stray read_text claims: {read_text_claims})",
    )
    expect(
        "ADV-SUITE-01" in record and "not a committed regression-selection" in record,
        "check25",
        "ADV-SUITE-01 is not recorded as tracked",
    )

    # 26. no implementation path in the frozen design scope
    offenders = sorted(p for p in changed if p.startswith(FORBIDDEN_PREFIXES))
    expect(not offenders, "check26", f"implementation paths in the design scope: {offenders}")
    expect(
        not [
            p
            for p in changed
            if re.search(r"(verify|test)_step66", p) and "design_unified_control_center" not in p
        ],
        "check26b",
        "a historical stage verifier or test is inside the design scope",
    )

    # 27. no implementation slice authorized
    auth = data.get("implementation_authorizations", {})
    for key, value in auth.items():
        if isinstance(value, str):
            expect(
                "NOT" in value.upper() or value.upper() in {"FALSE", "NONE"},
                "check27",
                f"implementation authorization {key} is {value!r}, expected not authorized",
            )
        elif isinstance(value, bool):
            expect(value is False, "check27", f"implementation authorization {key} is True")

    # 28. production execution count
    expect(
        data.get("production_executed_true_count") == 0,
        "check28",
        "manifest production_executed_true_count != 0",
    )
    expect(
        "production_executed_true_count: 0" in record,
        "check28b",
        "the merge record does not state production_executed_true_count: 0",
    )
    expect(
        f'DESIGN_STAGE_HEAD = "{DESIGN_STAGE_HEAD}"' in tests_src,
        "check29",
        "the design tests do not pin DESIGN_STAGE_HEAD",
    )

    print(f"  checks_run={checks_run}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] PR #26 merged as a non-squash two-parent merge; three design commits preserved;")
    print(
        "       positive design scope frozen to 9c5210d...bb8eab7 with an exact 14-path registry;"
    )
    print("       no positive HEAD endpoint; rejection guard still current-state; JSON manifest")
    print("       present and YAML absent; route truthfulness consistent across four sources;")
    print("       6/3/9 enums exact; 16 gaps; 5 mutation surfaces; Activity Timeline complete;")
    print("       OperatorConsole coexistence documented; R2-F01..F03 closed; advisories tracked")
    print("       only; no implementation authorized; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
