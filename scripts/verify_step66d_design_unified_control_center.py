#!/usr/bin/env python3
"""Step 66D-DESIGN -- Unified Control Center UX/IA design-package verifier.

Deterministic, read-only. Confirms the Step 66D-DESIGN package exists, is anchored to the canonical
baseline, freezes the Unified Control Center IA, preserves every binding 66D contract (six review
actions, three PO decisions, nine statuses, one QA rerun per version, blocking follow-up rule,
dual-anchor, legacy DeliveryPackage boundary), specifies all required states, and claims no
implementation.

Reads files on the current checkout and computes a local `git diff` against the canonical baseline
to confirm scope. Starts no runtime, container, database or external provider.

Marker: STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY"
BASELINE = "9c5210d190b82b76575ba8d456b5d2005c2867d2"
BASELINE_SHORT = "9c5210d"

D = ROOT / "docs" / "design" / "66d-delivery-acceptance"
H = ROOT / "docs" / "handoffs" / "66d-delivery-acceptance"

IA = D / "step66d-design-unified-control-center-ia.md"
ROUTES = D / "step66d-design-route-and-drilldown-map.md"
INBOX = D / "step66d-design-delivery-inbox-spec.md"
REVIEW = D / "step66d-design-delivery-review-interactions.md"
MATRIX = D / "step66d-design-state-error-permission-matrix.md"
WIRE = D / "step66d-design-wireframes.md"
A11Y = D / "step66d-design-accessibility-responsive-spec.md"
HANDOFF = D / "step66d-design-frontend-handoff.md"
MANIFEST = D / "step66d-design-contract-manifest.yaml"
INVENTORY = H / "step66d-design-existing-ui-route-inventory.md"
GAPS = H / "step66d-design-gap-and-dependency-register.md"
EVIDENCE = H / "step66d-design-evidence.md"

REQUIRED = [IA, ROUTES, INBOX, REVIEW, MATRIX, WIRE, A11Y, HANDOFF, MANIFEST, INVENTORY, GAPS, EVIDENCE]

REVIEW_ACTIONS = ["ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"]
PO_DECISIONS = ["ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED"]
STATUSES = [
    "DRAFT", "SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED", "QA_RERUN_REQUESTED",
    "ACCEPTED", "REJECTED", "ARCHIVED", "EXPIRED",
]
STATE_KINDS = ["loading", "empty", "partial", "stale", "inaccessible", "error", "unknown"]
EVIDENCE_STATES = ["COMPLETE", "PARTIAL", "MISSING", "STALE", "INACCESSIBLE", "UNKNOWN"]

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
LOCAL_PATH_SHAPES = re.compile(r"(C:\\Users|C:/Users|/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/)")

FORBIDDEN_SCOPE_PREFIXES = (
    "apps/", "agents/", "services/", "shared/", "migrations/", "infra/",
    "helm/", "k8s/", ".github/workflows/",
)

failures: list[str] = []
checks_run = 0


def check(ok: bool, msg: str) -> None:
    global checks_run
    checks_run += 1
    if not ok:
        failures.append(msg)
        print(f"  [FAIL] {msg}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def low(p: Path) -> str:
    return read(p).lower()


def all_text() -> str:
    return "\n".join(read(p) for p in REQUIRED)


def main() -> int:
    # 1. package exists
    for p in REQUIRED:
        check(p.is_file(), f"missing required artifact: {p.relative_to(ROOT)}")

    text = all_text()
    text_low = text.lower()

    # 2. baseline anchored
    check(BASELINE in text or BASELINE_SHORT in text, "canonical baseline 9c5210d not recorded")
    for p in (IA, ROUTES, MANIFEST, EVIDENCE):
        check(BASELINE in read(p) or BASELINE_SHORT in read(p),
              f"{p.name} does not record the canonical baseline")

    # 3. Unified Control Center is the single canonical IA
    check("unified control center" in low(IA), "IA doc does not name Unified Control Center")
    check("canonical_ia: \"Unified Control Center\"" in read(MANIFEST),
          "manifest does not set canonical_ia to Unified Control Center")
    check("unified overview + existing route drill-down" in text_low,
          "implementation principle 'Unified Overview + Existing Route Drill-down' missing")
    # 4. IA not re-marked unresolved
    for bad in ("ia is unresolved", "ia remains open", "ia still open", "ia undecided"):
        check(bad not in text_low, f"design package re-marks the IA as unresolved: '{bad}'")
    check("option_comparison: \"CLOSED / NOT REOPENED\"" in read(MANIFEST),
          "manifest does not record the option comparison as closed")

    # 5. three-surface separation
    for term in ("delivery inbox", "unified control center", "delivery review"):
        check(term in low(IA), f"IA doc missing surface responsibility: {term}")
    check("duplication-prevention rule" in low(IA), "IA doc missing duplication-prevention rule")

    # 6/7. review actions and PO decisions: exact sets, separated
    for a in REVIEW_ACTIONS:
        check(a in read(REVIEW), f"review action missing from interactions spec: {a}")
    for d in PO_DECISIONS:
        check(d in read(REVIEW), f"PO decision missing from interactions spec: {d}")
    check("exactly six" in low(REVIEW), "interactions spec does not state exactly six review actions")
    check("exactly three" in low(REVIEW), "interactions spec does not state exactly three decisions")
    check("visually and semantically separated" in low(REVIEW),
          "interactions spec does not require action/decision separation")
    # forbidden merges
    check("accepted_with_follow_up" not in low(REVIEW).split("review gate action panel")[1].split("product owner decision panel")[0]
          if "review gate action panel" in low(REVIEW) and "product owner decision panel" in low(REVIEW) else True,
          "ACCEPTED_WITH_FOLLOW_UP appears inside the Review Gate Action panel section")

    # 8. nine canonical statuses
    for s in STATUSES:
        check(s in read(MATRIX), f"canonical status missing from state matrix: {s}")

    # 9. QA rerun limit == 1 per submission version, backend-authoritative
    check("limit_per_submission_version: 1" in read(MANIFEST),
          "manifest does not record QA rerun limit of 1 per submission version")
    check("1 of 1" in read(REVIEW), "interactions spec does not show the 1-of-1 rerun quota")
    check("client_counter_allowed: false" in read(MANIFEST),
          "manifest does not forbid a client-side rerun counter")
    check("qa_rerun_limit_reached" in text_low, "QA_RERUN_LIMIT_REACHED handling missing")

    # 10. expired forbids accept/reject
    check("expired" in low(REVIEW), "expiry UX missing from interactions spec")
    check("disabled_when_expired" in read(MANIFEST), "manifest missing expiry disable list")
    m = read(MANIFEST)
    seg = m.split("disabled_when_expired:")[1].split("available_when_expired:")[0] if "disabled_when_expired:" in m else ""
    check("ACCEPT" in seg and "REJECT" in seg, "expiry does not disable ACCEPT and REJECT")

    # 11. blocking follow-up rule
    check("blocking_item_allowed: false" in m, "manifest does not forbid blocking follow-up items")
    check("blocking_follow_up_requires_changes" in text_low,
          "BLOCKING_FOLLOW_UP_REQUIRES_CHANGES rule missing")
    check("no auto-conversion" in text_low or "not auto-convert" in text_low,
          "blocking follow-up rule does not forbid auto-conversion")

    # 12. states: loading/empty/partial/stale/unknown/inaccessible/error + permission
    for st in STATE_KINDS:
        check(st in low(MATRIX), f"state matrix missing state: {st}")
    for es in EVIDENCE_STATES:
        check(es in read(MATRIX) or es in read(IA), f"evidence health state missing: {es}")
    check("never green" in low(MATRIX) or "never green" in low(IA),
          "UNKNOWN-is-not-green rule missing")

    # 13. identity not verified blocks final decision
    check("identity not verified" in low(MATRIX), "permission state 'identity not verified' missing")
    check("final_decision_requires_verified_identity: true" in m,
          "manifest does not require verified identity for a final decision")

    # 14. read model freshness
    check("as_of" in text and "is_stale" in text, "read-model freshness fields (as_of/is_stale) missing")
    check("eventually consistent" in text_low, "eventual consistency not stated")
    check("authority_rule" in m, "manifest missing the detail-route-wins authority rule")

    # 15. existing routes not faked as implemented
    check("planned / not implemented" in low(ROUTES) or "planned_not_implemented" in low(MANIFEST),
          "absent routes are not marked PLANNED / NOT IMPLEMENTED")
    check("placeholder" in low(INVENTORY), "inventory does not identify placeholder routes")
    check("44" in read(INVENTORY), "inventory does not record the measured route count")

    # 16. deep-link contract
    for prm in ("project_id", "delivery_submission_id", "delivery_review_task_id", "return_to"):
        check(prm in read(ROUTES), f"deep-link parameter missing from route map: {prm}")
    check("return behavior" in low(ROUTES), "route map missing return behavior contract")

    # 17. responsive + 18. accessibility
    for bp in ("1440", "1280", "1024", "768"):
        check(bp in read(A11Y), f"breakpoint missing from a11y/responsive spec: {bp}")
    for a in ("keyboard", "focus", "screen-reader", "reduced motion", "focus trap"):
        check(a in low(A11Y), f"accessibility requirement missing: {a}")

    # 19. no-implementation statements
    check("no frontend implementation" in text_low, "no-frontend-implementation statement missing")
    check("not authorized" in text_low, "not-authorized statement missing")
    check("codex_authorized: false" in m, "manifest does not record codex_authorized: false")
    check("merge authorization: \"NOT GRANTED\"" in m or 'merge_authorization: "NOT GRANTED"' in m,
          "manifest does not record merge authorization NOT GRANTED")

    # 21. legacy DeliveryPackage boundary
    check("legacy_delivery_package_repurposed: false" in m,
          "manifest does not assert the legacy DeliveryPackage is not repurposed")
    check("legacy_delivery_package_refs" in text, "legacy reference contract not mentioned")
    check("deliverysubmission" in text_low, "DeliverySubmission aggregate not named")

    # dual anchor
    check("dual" in text_low and "delivery_review_task_id" in text,
          "dual-anchor model not represented")
    check("task is not the agent execution source of truth" in text_low
          or "non-dispatching" in text_low,
          "Task-is-not-execution-source-of-truth boundary not stated")

    # 22. production count
    check("production_executed_true_count: 0" in text or "production_executed_true_count = 0" in text,
          "production_executed_true_count 0 not recorded")
    check("production_executed_true_count: 0" in m, "manifest missing production_executed_true_count: 0")

    # ADR-66D-09 unchanged
    check("adr_66d_09_modified: false" in m, "manifest does not assert ADR-66D-09 unmodified")
    check("task_roles_modified: false" in m, "manifest does not assert TASK_ROLES unmodified")

    # wireframes: 10
    wf = len(re.findall(r"^## WF-\d+", read(WIRE), flags=re.M))
    check(wf == 10, f"expected 10 wireframes, found {wf}")

    # secrets / local paths
    for p in REQUIRED:
        t = read(p)
        check(not SECRET_SHAPES.search(t), f"possible secret shape in {p.name}")
        check(not LOCAL_PATH_SHAPES.search(t), f"local absolute path committed in {p.name}")

    # scope: no runtime/backend path changed vs baseline
    try:
        r = subprocess.run(["git", "diff", "--name-only", f"{BASELINE}...HEAD"],
                           cwd=ROOT, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            check(False, "could not compute diff against the canonical baseline")
        else:
            changed = [l.strip().replace("\\", "/") for l in r.stdout.splitlines() if l.strip()]
            for path in changed:
                for pref in FORBIDDEN_SCOPE_PREFIXES:
                    check(not path.startswith(pref), f"forbidden path changed: {path}")
    except FileNotFoundError:
        check(False, "git unavailable; cannot confirm scope")

    print(f"  checks_run={checks_run}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] Step 66D-DESIGN package complete; baseline 9c5210d; Unified Control Center is the")
    print("       single canonical IA with Unified Overview + Existing Route Drill-down; three")
    print("       surfaces separated; 6 review actions / 3 PO decisions separated; 9 statuses;")
    print("       QA rerun=1 backend-authoritative; expiry blocks accept/reject; blocking follow-up")
    print("       rule present; all states specified; identity gate present; freshness present;")
    print("       absent routes marked planned; deep-link + responsive + a11y specified; legacy")
    print("       DeliveryPackage preserved; no implementation; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
