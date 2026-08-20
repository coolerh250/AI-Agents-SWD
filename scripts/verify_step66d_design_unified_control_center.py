#!/usr/bin/env python3
"""Step 66D-DESIGN (+ RM1) -- Unified Control Center UX/IA design-package verifier.

Deterministic, read-only. Confirms the Step 66D-DESIGN package exists at exactly the registered
path set, is anchored to the canonical baseline, freezes the Unified Control Center IA, preserves
every binding 66D contract (exact six review actions, exact three PO decisions, exact nine
statuses, one QA rerun per submission version, blocking follow-up rule, dual anchor, legacy
DeliveryPackage boundary), specifies all seven data states plus the permission dimension, and
claims no implementation.

RM1 hardening:
  * positive exact-scope assertion against an explicit path registry (no generic docs/ allowlist)
  * JSON manifest parsed with json.load; exact-set enum assertions (extra values are rejected)
  * route / navigation / mutation-surface counts re-derived from frontend source and compared
    against the manifest and the design documents (count tampering is rejected)
  * semantic IA-regression protection driven by the manifest enums, not fixed substrings
  * split, stable metrics: CHECK_DEFINITIONS (registry size) and ASSERTIONS_EXECUTED (runtime)

Starts no runtime, container, database or external provider. Only reads files and runs local
`git diff --name-only`.

Markers:
  STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY: PASS | FAIL
  DESIGN_RM1_SCOPE_EXACT / DESIGN_RM1_SOURCE_COUNTS / DESIGN_RM1_ENUM_INTEGRITY /
  DESIGN_RM1_ROUTE_TRUTHFULNESS / DESIGN_RM1_REGRESSION_CLOSURE
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

# AT-M2 remediation: the rejection window ends where an authorized successor milestone
# takes over; without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import successor_window_end  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def successor_window_end(_baseline: str = "") -> str:
        """Strictest fallback: with no lifecycle module the window stays HEAD-relative."""
        return "HEAD"

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY"

DESIGN_BASELINE = "9c5210d190b82b76575ba8d456b5d2005c2867d2"
DESIGN_BASELINE_SHORT = "9c5210d"

# Step 66D-DESIGN-M1 post-merge scope freeze.
#
# While PR #26 was open the positive scope was computed as DESIGN_BASELINE...HEAD, which was safe
# because HEAD was the PR head and was bounded by DESIGN_EXPECTED_PATHS. Now that the PR is merged,
# HEAD is main and advances with every later authorised stage, so it must never again be the
# positive endpoint: this stage's scope is the immutable range below. Later stages may add paths to
# main; they cannot widen, narrow or drift what THIS stage is proven to have changed.
DESIGN_STAGE_HEAD = "bb8eab70ee7fb252329fe05c4b7039c2ed0f694b"
DESIGN_POSITIVE_RANGE = f"{DESIGN_BASELINE}...{DESIGN_STAGE_HEAD}"

# The positive scope above is frozen, which is what stops it drifting. The current-state rejection
# guard must NOT be frozen with it -- a runtime or frontend path added by any later commit still has
# to be caught. This anchor is deliberately HEAD-relative, it feeds the denylist only, and it can
# never widen or satisfy the positive scope.
RUNTIME_GUARD_ANCHOR = DESIGN_BASELINE

DESIGN_DIR = "docs/design/66d-delivery-acceptance"
HANDOFF_DIR = "docs/handoffs/66d-delivery-acceptance"

# Step 66D-DESIGN-M1: artifacts that share the step66d-design-* filename prefix but belong to the
# MERGE stage, not to the design package. Listed by exact literal path -- this excludes exactly one
# known governance file, never a prefix or pattern, so any OTHER unregistered step66d-design-*
# document is still rejected (the Probe A / F03 guarantee is preserved).
MERGE_GOVERNANCE_ARTIFACTS = frozenset(
    {f"{HANDOFF_DIR}/step66d-design-m1-canonical-merge-record.md"}
)

# --- exact scope registry: the complete, closed set of paths this design stage may change ---
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

IA = ROOT / DESIGN_DIR / "step66d-design-unified-control-center-ia.md"
ROUTES_DOC = ROOT / DESIGN_DIR / "step66d-design-route-and-drilldown-map.md"
INBOX = ROOT / DESIGN_DIR / "step66d-design-delivery-inbox-spec.md"
REVIEW = ROOT / DESIGN_DIR / "step66d-design-delivery-review-interactions.md"
MATRIX = ROOT / DESIGN_DIR / "step66d-design-state-error-permission-matrix.md"
WIRE = ROOT / DESIGN_DIR / "step66d-design-wireframes.md"
A11Y = ROOT / DESIGN_DIR / "step66d-design-accessibility-responsive-spec.md"
HANDOFF = ROOT / DESIGN_DIR / "step66d-design-frontend-handoff.md"
MANIFEST = ROOT / DESIGN_DIR / "step66d-design-contract-manifest.json"
INVENTORY = ROOT / HANDOFF_DIR / "step66d-design-existing-ui-route-inventory.md"
GAPS = ROOT / HANDOFF_DIR / "step66d-design-gap-and-dependency-register.md"
EVIDENCE = ROOT / HANDOFF_DIR / "step66d-design-evidence.md"

DOC_FILES = [IA, ROUTES_DOC, INBOX, REVIEW, MATRIX, WIRE, A11Y, HANDOFF, INVENTORY, GAPS, EVIDENCE]

APP_TSX = ROOT / "apps/admin-console/src/App.tsx"
NAV_TSX = ROOT / "apps/admin-console/src/components/Nav.tsx"
PAGES_DIR = ROOT / "apps/admin-console/src/pages"
COMPONENTS_DIR = ROOT / "apps/admin-console/src/components"
FRONTEND_SRC = ROOT / "apps/admin-console/src"

EXPECTED_REVIEW_ACTIONS = frozenset(
    {"ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"}
)
EXPECTED_PO_DECISIONS = frozenset({"ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED"})
EXPECTED_STATUSES = frozenset(
    {
        "DRAFT",
        "SUBMITTED",
        "UNDER_REVIEW",
        "CHANGES_REQUESTED",
        "QA_RERUN_REQUESTED",
        "ACCEPTED",
        "REJECTED",
        "ARCHIVED",
        "EXPIRED",
    }
)
EXPECTED_DATA_STATES = frozenset(
    {"loading", "empty", "partial", "stale", "inaccessible", "error", "unknown"}
)
EXPECTED_PERMISSION_STATES = frozenset(
    {
        "authorized",
        "not_authorized",
        "identity_not_verified",
        "capability_unavailable",
        "read_only_observer",
        "future_shared_runtime_required",
    }
)

CANONICAL_IA = "UNIFIED_CONTROL_CENTER"
CANONICAL_PRINCIPLE = "UNIFIED_OVERVIEW_WITH_EXISTING_ROUTE_DRILL_DOWN"
NON_SELECTED_IA = "COORDINATED_EXISTING_ROUTES"

EXPECTED_MUTATION_SURFACES = frozenset(
    {
        "apps/admin-console/src/pages/TaskNew.tsx",
        "apps/admin-console/src/pages/TaskDetail.tsx",
        "apps/admin-console/src/pages/TaskWorkroom.tsx",
        "apps/admin-console/src/pages/MultiProjectDelivery.tsx",
        "apps/admin-console/src/pages/OperatorConsole.tsx",
    }
)

PLANNED_ABSENT_ROUTES = (
    "/projects/:projectId/control-center",
    "/delivery-submissions/:deliverySubmissionId/review",
)
EXPECTED_PLACEHOLDER_ROUTES = ("/delivery-inbox", "/delivery-detail")

# Sentences that assert the IA is still undecided, in any phrasing.
IA_OPEN_PATTERNS = (
    re.compile(
        r"\bIA\b[^.\n]{0,60}\b(remains?|is|stays?)\s+(open|unresolved|undecided|pending)",
        re.IGNORECASE,
    ),
    re.compile(r"final IA[^.\n]{0,40}\bnot\b[^.\n]{0,20}\bselected\b", re.IGNORECASE),
    re.compile(r"either approach[^.\n]{0,60}\bcanonical\b", re.IGNORECASE),
    re.compile(
        r"\b(information architecture|canonical IA)\b[^.\n]{0,60}\b(undecided|unresolved|not (yet )?(selected|chosen|decided))",
        re.IGNORECASE,
    ),
    re.compile(r"\bIA decision\b[^.\n]{0,40}\b(open|pending|outstanding)\b", re.IGNORECASE),
)
IA_HISTORICAL_CUES = (
    "previously",
    "historical",
    "superseded",
    "was recorded",
    "arch1 section 12",
    "no longer",
    "before this stage",
    "prior to",
    "originally",
)

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
LOCAL_PATH_SHAPES = re.compile(
    r"(C:\\Users|C:/Users|/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/)"
)

WRITE_VERB_RE = re.compile(r"""method:\s*["'](?:POST|PATCH|PUT|DELETE)["']""")
VERB_CONST_RE = re.compile(r"""(\w+)\s*=\s*["'](?:POST|PATCH|PUT|DELETE)["']""")

# --- RM2: route truthfulness across the three design representations -------------------
# Canonical classes a route may hold. Source (App.tsx) is authoritative.
CLASS_REAL_PAGE = "REAL_PAGE"
CLASS_PLACEHOLDER = "PLACEHOLDER"
CLASS_ABSENT = "ABSENT"

# Terms that assert a route is built/usable. A source PLACEHOLDER or ABSENT route may never be
# described with one of these unless the term is explicitly negated (e.g. "NOT IMPLEMENTED").
IMPLEMENTED_TERMS = (
    "IMPLEMENTED",
    "FUNCTIONAL",
    "AVAILABLE",
    "ACTIVE",
    "READY",
    "PRODUCTION_READY",
    "PRODUCTION READY",
    "WRITE_ENABLED",
    "WRITE ENABLED",
    "REAL_PAGE",
)
PLACEHOLDER_TERMS = ("PLACEHOLDER",)
ABSENT_TERMS = ("ABSENT", "PLANNED")
# A negation immediately preceding an implemented term neutralises it.
NEGATION_PREFIX = re.compile(r"(NOT|NEVER|NO)\s*[/_-]?\s*$", re.IGNORECASE)


def classify_state_text(text: str) -> str | None:
    """Normalise a design-representation state string into a canonical route class.

    Negation-aware: "PLANNED / NOT IMPLEMENTED" classifies as ABSENT, not REAL_PAGE. This is a
    structural classification, not a naked substring blacklist.
    """
    upper = (text or "").upper()
    positive_implemented = False
    for term in IMPLEMENTED_TERMS:
        for match in re.finditer(re.escape(term), upper):
            if not NEGATION_PREFIX.search(upper[: match.start()]):
                positive_implemented = True
                break
        if positive_implemented:
            break
    has_placeholder = any(term in upper for term in PLACEHOLDER_TERMS)
    has_absent = any(term in upper for term in ABSENT_TERMS)
    if has_placeholder:
        return CLASS_PLACEHOLDER
    if has_absent:
        return CLASS_ABSENT
    if positive_implemented:
        return CLASS_REAL_PAGE
    return None


# --- check registry: stable named definitions (RM1 metric F09) ---
CHECK_IDS = (
    "scope.exact_path_set",
    "scope.no_frontend_or_runtime_path",
    "artifacts.all_present",
    "artifacts.no_unregistered_design_document",
    "baseline.recorded",
    "manifest.valid_json",
    "manifest.required_keys",
    "ia.canonical_enum",
    "ia.principle_enum",
    "ia.single_active_declaration",
    "ia.no_open_decision_wording",
    "ia.alternative_is_historical_only",
    "enum.review_actions_exact",
    "enum.po_decisions_exact",
    "enum.statuses_exact",
    "enum.no_cross_contamination",
    "states.data_states_exact",
    "states.permission_states_exact",
    "states.activity_timeline_unknown_cell",
    "states.section_rows_have_seven_cells",
    "counts.routes_match_source",
    "counts.nav_match_source",
    "counts.badges_named_and_match_source",
    "counts.frontend_files_match_source",
    "counts.mutation_surfaces_match_source",
    "counts.gaps_match_register",
    "counts.wireframes_match_docs",
    "counts.component_candidates_match_manifest",
    "counts.acceptance_criteria_match_manifest",
    "routes.classification_matches_source",
    "routes.no_duplicate_paths",
    "routes.absent_not_marked_implemented",
    "routes.placeholder_not_marked_functional",
    "routes.semantic_routes_classification",
    "routes.document_classification",
    "routes.cross_representation_equality",
    "qa_rerun.limit_one_backend_authoritative",
    "expiry.blocks_accept_and_reject",
    "follow_up.blocking_rule",
    "identity.final_decision_gate",
    "read_model.freshness_contract",
    "deep_link.parameter_contract",
    "responsive.breakpoints",
    "accessibility.requirements",
    "legacy.delivery_package_boundary",
    "dual_anchor.model_present",
    "operator_console.duplication_analysis",
    "inbox.filter_terminology_disambiguated",
    "no_implementation.claims",
    "security.no_secret_shapes",
    "security.no_local_absolute_paths",
    "production.executed_count_zero",
)
CHECK_DEFINITIONS = len(CHECK_IDS)

failures: list[str] = []
assertions_executed = 0


def expect(condition: bool, check_id: str, message: str) -> None:
    """Record one executed assertion against a registered check id."""
    global assertions_executed
    assertions_executed += 1
    if check_id not in CHECK_IDS:
        failures.append(f"[registry] unregistered check id: {check_id}")
        return
    if not condition:
        failures.append(f"{check_id}: {message}")
        print(f"  [FAIL] {check_id}: {message}")


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def strip_ts_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)


def brace_body(text: str, open_index: int) -> str:
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[open_index : index + 1]
    return text[open_index:]


# ---------------------------------------------------------------- source parsers
def parse_routes() -> list[dict[str, str]]:
    text = strip_ts_comments(read(APP_TSX))
    routes: list[dict[str, str]] = []
    for block in re.split(r"(?=<Route\b)", text):
        match = re.search(r'path="([^"]+)"', block)
        if not match:
            continue
        placeholder = "PlaceholderPage" in block
        element = re.search(r"element=\{\s*<\s*(\w+)", block)
        routes.append(
            {
                "path": match.group(1),
                "component": (
                    "PlaceholderPage"
                    if placeholder
                    else (element.group(1) if element else "unknown")
                ),
                "classification": "PLACEHOLDER" if placeholder else "REAL_PAGE",
            }
        )
    return routes


def parse_nav() -> dict[str, object]:
    text = strip_ts_comments(read(NAV_TSX))
    badges = re.findall(r'badge:\s*"([\w-]+)"', text)
    return {
        "items": len(re.findall(r'to:\s*"([^"]+)",\s*label:\s*"([^"]+)"', text)),
        "groups": len(re.findall(r'id:\s*"([^"]+)",\s*\n\s*label:\s*"([^"]+)"', text)),
        "badges": {
            "read_only": badges.count("Read-only"),
            "soon": badges.count("Soon"),
            "evidence": badges.count("Evidence"),
        },
    }


def parse_mutation_surfaces() -> set[str]:
    """Semantic write-surface detection: private write helper + transitive import/call trace."""
    texts: dict[pathlib.Path, str] = {}
    for path in FRONTEND_SRC.rglob("*.ts*"):
        if "__tests__" in str(path):
            continue
        texts[path] = strip_ts_comments(read(path))

    def is_write_body(body: str) -> bool:
        if WRITE_VERB_RE.search(body):
            return True
        for name in VERB_CONST_RE.findall(body):
            if re.search(r"method:\s*" + re.escape(name) + r"\b", body):
                return True
        return False

    write_methods: set[str] = set()
    for path, text in texts.items():
        helpers: list[str] = []
        for match in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*<?[^{]*\{", text):
            body = brace_body(text, text.index("{", match.end() - 1))
            if is_write_body(body):
                helpers.append(match.group(1))
        if not helpers:
            continue
        for match in re.finditer(r"export\s+const\s+(\w+)\s*=\s*\{", text):
            obj_body = brace_body(text, text.index("{", match.end() - 1))
            for part in re.split(r"\n  (?=(?:async\s+)?\w+\s*[(<])", obj_body):
                name = re.match(r"\s*(?:async\s+)?(\w+)", part)
                if name and any(
                    re.search(r"\b" + re.escape(h) + r"\s*[(<]", part) for h in helpers
                ):
                    write_methods.add(name.group(1))
        for match in re.finditer(r"export\s+(?:async\s+)?function\s+(\w+)\s*<?[^{]*\{", text):
            body = brace_body(text, text.index("{", match.end() - 1))
            if any(re.search(r"\b" + re.escape(h) + r"\s*[(<]", body) for h in helpers):
                write_methods.add(match.group(1))

    ordered = sorted(write_methods)

    def calls_write(text: str) -> bool:
        return any(re.search(r"\.\s*" + re.escape(m) + r"\s*\(", text) for m in ordered)

    by_stem: dict[str, list[pathlib.Path]] = {}
    for path in texts:
        by_stem.setdefault(path.stem, []).append(path)

    memo: dict[pathlib.Path, bool] = {}

    def reaches(path: pathlib.Path, seen: frozenset[pathlib.Path] = frozenset()) -> bool:
        if path in memo:
            return memo[path]
        if path in seen:
            return False
        seen = seen | {path}
        if calls_write(texts[path]):
            memo[path] = True
            return True
        for imported in re.findall(r"""from\s+["']\.{1,2}/([^"']+)["']""", texts[path]):
            for target in by_stem.get(pathlib.Path(imported).name, []):
                if reaches(target, seen):
                    memo[path] = True
                    return True
        memo[path] = False
        return False

    return {
        str(p.relative_to(ROOT)).replace("\\", "/") for p in PAGES_DIR.glob("*.tsx") if reaches(p)
    }


def _git_changed(rev_range: str) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", rev_range],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def changed_paths() -> list[str] | None:
    """Positive scope: the frozen DESIGN_BASELINE...DESIGN_STAGE_HEAD range, never current HEAD."""
    return _git_changed(DESIGN_POSITIVE_RANGE)


def current_state_paths() -> list[str] | None:
    """Rejection-only guard input: deliberately HEAD-relative so later commits stay scanned."""
    return _git_changed(
        f"{RUNTIME_GUARD_ANCHOR}...{successor_window_end(RUNTIME_GUARD_ANCHOR)}"
    )


# ---------------------------------------------------------------- checks
def check_scope() -> None:
    changed = changed_paths()
    expect(
        changed is not None,
        "scope.exact_path_set",
        "could not compute the diff against DESIGN_BASELINE",
    )
    if changed is None:
        return
    actual = set(changed)
    expect(
        actual == DESIGN_EXPECTED_PATHS,
        "scope.exact_path_set",
        "changed-path set != DESIGN_EXPECTED_PATHS; "
        f"missing={sorted(DESIGN_EXPECTED_PATHS - actual)} "
        f"unexpected={sorted(actual - DESIGN_EXPECTED_PATHS)}",
    )
    forbidden = (
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
    # Rejection-only, and deliberately evaluated against CURRENT state rather than the frozen
    # positive range, so a runtime path introduced by any later commit is still caught. This never
    # admits a path into the positive scope asserted above.
    current = current_state_paths()
    scanned = set(current) if current is not None else actual
    offenders = sorted(p for p in scanned if p.startswith(forbidden))
    expect(
        not offenders,
        "scope.no_frontend_or_runtime_path",
        f"frontend/runtime paths changed: {offenders}",
    )


def check_artifacts() -> None:
    for path in [*DOC_FILES, MANIFEST]:
        expect(
            path.is_file(), "artifacts.all_present", f"missing artifact: {path.relative_to(ROOT)}"
        )
    registered_docs = {p for p in DESIGN_EXPECTED_PATHS if p.startswith((DESIGN_DIR, HANDOFF_DIR))}
    on_disk = {
        str(p.relative_to(ROOT)).replace("\\", "/")
        for directory in (ROOT / DESIGN_DIR, ROOT / HANDOFF_DIR)
        for p in directory.glob("*")
        if p.is_file() and p.name.startswith("step66d-design-")
    } - MERGE_GOVERNANCE_ARTIFACTS
    expect(
        on_disk == registered_docs,
        "artifacts.no_unregistered_design_document",
        f"unregistered design document(s): {sorted(on_disk - registered_docs)}; "
        f"missing registered: {sorted(registered_docs - on_disk)}",
    )


def check_baseline(manifest: dict) -> None:
    for path in (IA, ROUTES_DOC, EVIDENCE):
        text = read(path)
        expect(
            DESIGN_BASELINE in text or DESIGN_BASELINE_SHORT in text,
            "baseline.recorded",
            f"{path.name} does not record the canonical baseline",
        )
    expect(
        manifest.get("canonical_baseline", {}).get("main") == DESIGN_BASELINE,
        "baseline.recorded",
        "manifest canonical_baseline.main != DESIGN_BASELINE",
    )


def check_manifest_shape(manifest: dict) -> None:
    required = (
        "canonical_baseline",
        "canonical_ia",
        "implementation_principle",
        "semantic_routes",
        "surface_responsibilities",
        "canonical_statuses",
        "review_gate_actions",
        "product_owner_decisions",
        "required_data_states",
        "permission_states",
        "wireframes",
        "component_candidates",
        "acceptance_criteria",
        "open_gaps",
        "route_inventory",
        "frontend_inventory",
        "implementation_authorizations",
        "production_executed_true_count",
    )
    for key in required:
        expect(key in manifest, "manifest.required_keys", f"manifest missing required key: {key}")


def check_ia(manifest: dict) -> None:
    expect(
        manifest.get("canonical_ia") == CANONICAL_IA,
        "ia.canonical_enum",
        f"canonical_ia != {CANONICAL_IA} (got {manifest.get('canonical_ia')!r})",
    )
    expect(
        manifest.get("implementation_principle") == CANONICAL_PRINCIPLE,
        "ia.principle_enum",
        f"implementation_principle != {CANONICAL_PRINCIPLE} "
        f"(got {manifest.get('implementation_principle')!r})",
    )
    decision = manifest.get("ia_decision", {})
    expect(
        decision.get("non_selected_alternative") == NON_SELECTED_IA,
        "ia.alternative_is_historical_only",
        "manifest does not record the non-selected alternative explicitly",
    )
    expect(
        "SUPERSEDED" in str(decision.get("non_selected_alternative_status", "")).upper()
        or "HISTORICAL" in str(decision.get("non_selected_alternative_status", "")).upper(),
        "ia.alternative_is_historical_only",
        "non-selected alternative is not marked superseded/historical",
    )

    declarations = 0
    for path in DOC_FILES:
        for line in read(path).splitlines():
            if re.search(r"canonical_ia\s*[:=]\s*\"?UNIFIED_CONTROL_CENTER", line):
                declarations += 1
    expect(
        declarations <= 1,
        "ia.single_active_declaration",
        f"more than one active canonical_ia declaration in design documents ({declarations})",
    )

    for path in DOC_FILES:
        text = read(path)
        for pattern in IA_OPEN_PATTERNS:
            for match in pattern.finditer(text):
                start = max(0, match.start() - 200)
                context = text[start : match.end() + 120].lower()
                historical = any(cue in context for cue in IA_HISTORICAL_CUES)
                expect(
                    historical,
                    "ia.no_open_decision_wording",
                    f"{path.name}: IA described as open/undecided without historical context: "
                    f"{match.group(0)!r}",
                )

    for path in DOC_FILES:
        text = read(path)
        for match in re.finditer(r"Coordinated Existing Routes", text, re.IGNORECASE):
            start = max(0, match.start() - 260)
            context = text[start : match.end() + 160].lower()
            ok = (
                any(cue in context for cue in IA_HISTORICAL_CUES)
                or "not selected" in context
                or "non-selected" in context
                or "still open" in context
                or "owner" in context
            )
            expect(
                ok,
                "ia.alternative_is_historical_only",
                f"{path.name}: the non-selected alternative appears without historical or "
                "not-selected framing",
            )


def check_enums(manifest: dict) -> None:
    actions = set(manifest.get("review_gate_actions", []))
    decisions = set(manifest.get("product_owner_decisions", []))
    statuses = set(manifest.get("canonical_statuses", []))
    expect(
        actions == EXPECTED_REVIEW_ACTIONS,
        "enum.review_actions_exact",
        f"review_gate_actions != exact six; extra={sorted(actions - EXPECTED_REVIEW_ACTIONS)} "
        f"missing={sorted(EXPECTED_REVIEW_ACTIONS - actions)}",
    )
    expect(
        len(manifest.get("review_gate_actions", [])) == 6,
        "enum.review_actions_exact",
        "review_gate_actions is not exactly 6 entries",
    )
    expect(
        decisions == EXPECTED_PO_DECISIONS,
        "enum.po_decisions_exact",
        f"product_owner_decisions != exact three; extra={sorted(decisions - EXPECTED_PO_DECISIONS)} "
        f"missing={sorted(EXPECTED_PO_DECISIONS - decisions)}",
    )
    expect(
        len(manifest.get("product_owner_decisions", [])) == 3,
        "enum.po_decisions_exact",
        "product_owner_decisions is not exactly 3 entries",
    )
    expect(
        statuses == EXPECTED_STATUSES,
        "enum.statuses_exact",
        f"canonical_statuses != exact nine; extra={sorted(statuses - EXPECTED_STATUSES)} "
        f"missing={sorted(EXPECTED_STATUSES - statuses)}",
    )
    expect(
        len(manifest.get("canonical_statuses", [])) == 9,
        "enum.statuses_exact",
        "canonical_statuses is not exactly 9 entries",
    )
    expect(
        "ACCEPTED_WITH_FOLLOW_UP" not in actions,
        "enum.no_cross_contamination",
        "ACCEPTED_WITH_FOLLOW_UP must never appear in the Review Gate Action enum",
    )
    for forbidden in ("REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"):
        expect(
            forbidden not in decisions,
            "enum.no_cross_contamination",
            f"{forbidden} must never appear in the Product Owner Decision enum",
        )


def check_states(manifest: dict) -> None:
    data_states = set(manifest.get("required_data_states", []))
    perm_states = set(manifest.get("permission_states", []))
    expect(
        data_states == EXPECTED_DATA_STATES,
        "states.data_states_exact",
        f"required_data_states != exact seven; got {sorted(data_states)}",
    )
    expect(
        perm_states == EXPECTED_PERMISSION_STATES,
        "states.permission_states_exact",
        f"permission_states != exact six; got {sorted(perm_states)}",
    )
    expect(
        manifest.get("state_matrix", {}).get("activity_timeline_has_unknown_state") is True,
        "states.activity_timeline_unknown_cell",
        "manifest does not assert the Activity Timeline unknown state",
    )
    expect(
        manifest.get("state_matrix", {}).get("unknown_is_distinct_from_error") is True,
        "states.activity_timeline_unknown_cell",
        "manifest does not assert unknown is distinct from error",
    )

    matrix_text = read(MATRIX)
    rows = [
        line
        for line in matrix_text.splitlines()
        if line.startswith("| ")
        and line.count("|") >= 8
        and not line.startswith("| ---")
        and "loading" not in line.lower()[:40]
    ]
    timeline_rows = [r for r in rows if r.lower().startswith("| activity timeline")]
    expect(
        len(timeline_rows) == 1,
        "states.activity_timeline_unknown_cell",
        "Activity Timeline row not found exactly once in the data-state matrix",
    )
    for row in timeline_rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        expect(
            len(cells) == 8 and all(cells),
            "states.section_rows_have_seven_cells",
            f"Activity Timeline row does not have 7 populated data-state cells: {len(cells) - 1}",
        )
        if len(cells) == 8:
            expect(
                "unknown" in cells[7].lower(),
                "states.activity_timeline_unknown_cell",
                "Activity Timeline unknown cell does not describe an UNKNOWN behavior",
            )


def check_counts(manifest: dict) -> None:
    routes = parse_routes()
    nav = parse_nav()
    mutations = parse_mutation_surfaces()
    counts = manifest.get("measured_counts", {})
    inventory_text = read(INVENTORY)
    manifest_routes = manifest.get("route_inventory", {})

    total = len(routes)
    placeholders = sum(1 for r in routes if r["classification"] == "PLACEHOLDER")
    real_pages = total - placeholders

    expect(
        manifest_routes.get("total_routes") == total,
        "counts.routes_match_source",
        f"manifest total_routes={manifest_routes.get('total_routes')} but source has {total}",
    )
    expect(
        manifest_routes.get("placeholder_routes") == placeholders,
        "counts.routes_match_source",
        f"manifest placeholder_routes != source ({placeholders})",
    )
    expect(
        manifest_routes.get("real_page_routes") == real_pages,
        "counts.routes_match_source",
        f"manifest real_page_routes != source ({real_pages})",
    )
    expect(
        counts.get("routes_declared") == total,
        "counts.routes_match_source",
        "measured_counts.routes_declared != source",
    )
    expect(
        re.search(rf"\|\s*Routes declared\s*\|\s*\*\*{total}\*\*", inventory_text) is not None,
        "counts.routes_match_source",
        f"inventory does not report the source route count ({total})",
    )

    expect(
        manifest.get("navigation_inventory", {}).get("nav_items") == nav["items"],
        "counts.nav_match_source",
        "manifest nav_items != source",
    )
    expect(
        manifest.get("navigation_inventory", {}).get("nav_groups") == nav["groups"],
        "counts.nav_match_source",
        "manifest nav_groups != source",
    )
    manifest_badges = manifest.get("navigation_inventory", {}).get("badges", {})
    expect(
        set(manifest_badges) == {"read_only", "soon", "evidence"},
        "counts.badges_named_and_match_source",
        f"badge counts must use named keys; got {sorted(manifest_badges)}",
    )
    expect(
        manifest_badges == nav["badges"],
        "counts.badges_named_and_match_source",
        f"manifest badges {manifest_badges} != source {nav['badges']}",
    )

    page_files = len(list(PAGES_DIR.glob("*.tsx")))
    component_files = len(list(COMPONENTS_DIR.glob("*.tsx")))
    frontend = manifest.get("frontend_inventory", {})
    expect(
        frontend.get("page_files") == page_files,
        "counts.frontend_files_match_source",
        "manifest page_files != source",
    )
    expect(
        frontend.get("component_files") == component_files,
        "counts.frontend_files_match_source",
        "manifest component_files != source",
    )

    manifest_mutations = {m["source_path"] for m in frontend.get("mutation_surfaces", [])}
    expect(
        mutations == EXPECTED_MUTATION_SURFACES,
        "counts.mutation_surfaces_match_source",
        f"source-derived mutation surfaces != expected registry; got {sorted(mutations)}",
    )
    expect(
        manifest_mutations == mutations,
        "counts.mutation_surfaces_match_source",
        f"manifest mutation surfaces != source-derived; manifest={sorted(manifest_mutations)}",
    )
    expect(
        frontend.get("mutation_surface_count") == len(mutations),
        "counts.mutation_surfaces_match_source",
        "manifest mutation_surface_count != source",
    )
    expect(
        counts.get("mutation_surfaces") == len(mutations),
        "counts.mutation_surfaces_match_source",
        "measured_counts.mutation_surfaces != source",
    )
    expect(
        re.search(
            rf"\|\s*Semantic mutation surfaces \(pages\)\s*\|\s*\*\*{len(mutations)}\*\*",
            inventory_text,
        )
        is not None,
        "counts.mutation_surfaces_match_source",
        "inventory does not report the corrected mutation-surface count",
    )

    gap_ids = re.findall(r"^### (DG-\d+)", read(GAPS), flags=re.MULTILINE)
    expect(
        len(gap_ids) == len(manifest.get("open_gaps", [])),
        "counts.gaps_match_register",
        f"gap register has {len(gap_ids)} DG entries but manifest lists "
        f"{len(manifest.get('open_gaps', []))}",
    )
    expect(
        counts.get("open_gaps") == len(gap_ids),
        "counts.gaps_match_register",
        "measured_counts.open_gaps != gap register",
    )
    expect(
        re.search(rf"Total gaps:\s*{len(gap_ids)}\b", read(GAPS)) is not None,
        "counts.gaps_match_register",
        "gap register summary total != DG heading count",
    )

    wireframes = re.findall(r"^## (WF-\d+)", read(WIRE), flags=re.MULTILINE)
    expect(
        len(wireframes) == len(manifest.get("wireframes", [])),
        "counts.wireframes_match_docs",
        f"wireframe doc has {len(wireframes)} but manifest lists "
        f"{len(manifest.get('wireframes', []))}",
    )
    expect(
        counts.get("wireframes") == len(wireframes),
        "counts.wireframes_match_docs",
        "measured_counts.wireframes != wireframe headings",
    )

    expect(
        counts.get("component_candidates") == len(manifest.get("component_candidates", [])),
        "counts.component_candidates_match_manifest",
        "measured_counts.component_candidates != component_candidates length",
    )
    expect(
        counts.get("acceptance_criteria") == len(manifest.get("acceptance_criteria", [])),
        "counts.acceptance_criteria_match_manifest",
        "measured_counts.acceptance_criteria != acceptance_criteria length",
    )


def check_route_truthfulness(manifest: dict) -> None:
    routes = parse_routes()
    by_path = {r["path"]: r for r in routes}
    manifest_routes = manifest.get("route_inventory", {}).get("routes", [])

    expect(
        len(by_path) == len(routes),
        "routes.no_duplicate_paths",
        "duplicate route paths detected in source",
    )
    manifest_by_path = {r["path"]: r for r in manifest_routes}
    expect(
        set(manifest_by_path) == set(by_path),
        "routes.classification_matches_source",
        f"manifest route set != source; missing={sorted(set(by_path) - set(manifest_by_path))} "
        f"extra={sorted(set(manifest_by_path) - set(by_path))}",
    )
    for path, source_route in by_path.items():
        entry = manifest_by_path.get(path)
        if entry is None:
            continue
        expect(
            entry.get("classification") == source_route["classification"],
            "routes.classification_matches_source",
            f"{path}: manifest says {entry.get('classification')} but source says "
            f"{source_route['classification']}",
        )

    planned = {
        r["path"]: r for r in manifest.get("route_inventory", {}).get("planned_absent_routes", [])
    }
    for path in PLANNED_ABSENT_ROUTES:
        expect(
            path not in by_path,
            "routes.absent_not_marked_implemented",
            f"{path} is declared absent but exists in App.tsx",
        )
        entry = planned.get(path, {})
        expect(
            entry.get("classification") == "ABSENT_PLANNED",
            "routes.absent_not_marked_implemented",
            f"{path} is not recorded as ABSENT_PLANNED in the manifest",
        )
        expect(
            "IMPLEMENTED" not in str(entry.get("classification", "")).replace("ABSENT_PLANNED", ""),
            "routes.absent_not_marked_implemented",
            f"{path} must not be marked implemented",
        )

    for path in EXPECTED_PLACEHOLDER_ROUTES:
        placeholder_route = by_path.get(path)
        expect(
            placeholder_route is not None and placeholder_route["classification"] == "PLACEHOLDER",
            "routes.placeholder_not_marked_functional",
            f"{path} is expected to be a PLACEHOLDER route in source",
        )
        entry = manifest_by_path.get(path, {})
        expect(
            entry.get("classification") == "PLACEHOLDER",
            "routes.placeholder_not_marked_functional",
            f"{path} must be recorded as PLACEHOLDER, not functional",
        )

    semantic = {r.get("route"): r for r in manifest.get("semantic_routes", [])}
    for path in PLANNED_ABSENT_ROUTES:
        entry = semantic.get(path, {})
        expect(
            entry.get("current_state") == "PLANNED_NOT_IMPLEMENTED",
            "routes.absent_not_marked_implemented",
            f"semantic_routes[{path}] must be PLANNED_NOT_IMPLEMENTED",
        )


def parse_route_map_document() -> dict[str, str]:
    """Extract {route path -> raw state cell} from the route responsibility matrix.

    Structural, not document-wide: locate the table whose header declares an implemented-state
    column, then read only that table's body rows. Other tables in the document (for example the
    OperatorConsole contract-difference comparison) are deliberately not route classifications and
    must not be parsed as such.
    """
    entries: dict[str, str] = {}
    lines = read(ROUTES_DOC).splitlines()
    in_table = False
    route_col = state_col = -1
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        lowered = [c.lower() for c in cells]
        if "implemented state" in lowered:
            in_table = True
            state_col = lowered.index("implemented state")
            route_col = lowered.index("actual route") if "actual route" in lowered else 1
            continue
        if not in_table or stripped.startswith("| ---"):
            continue
        if len(cells) <= max(route_col, state_col):
            continue
        for route in re.findall(r"`(/[^`]*)`", cells[route_col]):
            entries[route] = cells[state_col]
    return entries


def check_route_truthfulness_across_representations(manifest: dict) -> None:
    """RM2 / R2-F01: source is authoritative; all three design representations must agree.

    Representations: (A) manifest route_inventory.routes, (B) manifest semantic_routes,
    (C) the route-and-drilldown-map Markdown table. A route the source says is a PLACEHOLDER or
    ABSENT may never be described as implemented/functional/available in any of them.
    """
    source: dict[str, str] = {}
    for route in parse_routes():
        source[route["path"]] = (
            CLASS_PLACEHOLDER if route["classification"] == "PLACEHOLDER" else CLASS_REAL_PAGE
        )
    for path in PLANNED_ABSENT_ROUTES:
        if path not in source:
            source[path] = CLASS_ABSENT

    def compare(representation: str, check_id: str, entries: dict[str, str]) -> None:
        for path, raw in entries.items():
            expected = source.get(path)
            if expected is None:
                expect(
                    classify_state_text(raw) != CLASS_REAL_PAGE,
                    check_id,
                    f"{representation}: {path} is not present in App.tsx yet is described as "
                    f"implemented ({raw!r})",
                )
                continue
            actual = classify_state_text(raw)
            expect(
                actual is not None,
                check_id,
                f"{representation}: {path} has an unclassifiable state {raw!r}",
            )
            if actual is None:
                continue
            expect(
                actual == expected,
                check_id,
                f"{representation}: {path} is described as {actual} but App.tsx says {expected} "
                f"(cell {raw!r})",
            )
            if expected in (CLASS_PLACEHOLDER, CLASS_ABSENT):
                expect(
                    actual != CLASS_REAL_PAGE,
                    "routes.placeholder_not_marked_functional",
                    f"{representation}: {expected} route {path} is described as functional "
                    f"({raw!r})",
                )

    # (A) route_inventory.routes
    compare(
        "route_inventory.routes",
        "routes.classification_matches_source",
        {
            r["path"]: r.get("classification", "")
            for r in manifest.get("route_inventory", {}).get("routes", [])
        },
    )
    # (A2) planned_absent_routes
    compare(
        "route_inventory.planned_absent_routes",
        "routes.absent_not_marked_implemented",
        {
            r["path"]: r.get("classification", "")
            for r in manifest.get("route_inventory", {}).get("planned_absent_routes", [])
        },
    )
    # (B) semantic_routes
    compare(
        "semantic_routes",
        "routes.semantic_routes_classification",
        {
            r["route"]: r.get("current_state", "")
            for r in manifest.get("semantic_routes", [])
            if r.get("route")
        },
    )
    # (C) route-map Markdown table
    document_entries = parse_route_map_document()
    expect(
        len(document_entries) > 0,
        "routes.document_classification",
        "route-map document: no route responsibility rows parsed",
    )
    compare("route-map document", "routes.document_classification", document_entries)

    # Cross-representation equality on the intersection of registered routes.
    inventory = {
        r["path"]: classify_state_text(r.get("classification", ""))
        for r in manifest.get("route_inventory", {}).get("routes", [])
    }
    semantic = {
        r["route"]: classify_state_text(r.get("current_state", ""))
        for r in manifest.get("semantic_routes", [])
        if r.get("route")
    }
    document = {path: classify_state_text(raw) for path, raw in document_entries.items()}
    for path in set(semantic) | set(document):
        for name, mapping in (("semantic_routes", semantic), ("route-map document", document)):
            if path in mapping and path in inventory:
                expect(
                    mapping[path] == inventory[path],
                    "routes.cross_representation_equality",
                    f"{name} says {mapping[path]} for {path} but route_inventory says "
                    f"{inventory[path]}",
                )


def check_contracts(manifest: dict) -> None:
    review = read(REVIEW)
    qa = manifest.get("qa_rerun", {})
    expect(
        qa.get("limit_per_submission_version") == 1,
        "qa_rerun.limit_one_backend_authoritative",
        "QA rerun limit per submission version != 1",
    )
    expect(
        qa.get("client_counter_allowed") is False,
        "qa_rerun.limit_one_backend_authoritative",
        "client counter is not forbidden",
    )
    expect(
        "backend-authoritative" in str(qa.get("counter_source", "")).lower()
        or "persisted" in str(qa.get("counter_source", "")).lower(),
        "qa_rerun.limit_one_backend_authoritative",
        "counter source is not authoritative",
    )
    expect(
        "1 of 1" in review,
        "qa_rerun.limit_one_backend_authoritative",
        "interactions spec does not show the 1-of-1 quota",
    )

    disabled = set(manifest.get("expiry_rules", {}).get("disabled_when_expired", []))
    expect(
        {"ACCEPT", "REJECT"} <= disabled,
        "expiry.blocks_accept_and_reject",
        f"expiry does not disable ACCEPT and REJECT; got {sorted(disabled)}",
    )
    expect(
        "RERUN_QA" in disabled,
        "expiry.blocks_accept_and_reject",
        "expiry does not disable RERUN_QA",
    )

    follow_up = manifest.get("follow_up_rules", {})
    expect(
        follow_up.get("blocking_item_allowed") is False,
        "follow_up.blocking_rule",
        "blocking follow-up items are not forbidden",
    )
    expect(
        "REQUEST_CHANGES" in str(follow_up.get("blocking_item_behavior", "")).upper(),
        "follow_up.blocking_rule",
        "blocking follow-up does not direct to REQUEST_CHANGES",
    )
    expect(
        "BLOCKING_FOLLOW_UP_REQUIRES_CHANGES" in read(MATRIX) + review,
        "follow_up.blocking_rule",
        "canonical blocking follow-up error is not documented",
    )

    identity = manifest.get("identity", {})
    expect(
        identity.get("final_decision_requires_verified_identity") is True,
        "identity.final_decision_gate",
        "verified identity is not required for a final decision",
    )
    expect(
        identity.get("request_provided_identity_authoritative") is False,
        "identity.final_decision_gate",
        "request-provided identity must never be authoritative",
    )
    expect(
        "identity not verified" in read(MATRIX).lower(),
        "identity.final_decision_gate",
        "permission matrix does not include identity-not-verified",
    )

    read_model = manifest.get("read_model", {})
    expect(
        read_model.get("consistency") == "EVENTUALLY_CONSISTENT",
        "read_model.freshness_contract",
        "read model is not declared eventually consistent",
    )
    expect(
        set(read_model.get("required_fields", [])) >= {"as_of", "is_stale"},
        "read_model.freshness_contract",
        "read model does not require as_of/is_stale",
    )
    expect(
        "UNKNOWN" in str(read_model.get("missing_source_behavior", "")).upper(),
        "read_model.freshness_contract",
        "missing source does not render as UNKNOWN",
    )

    params = set(manifest.get("deep_link_parameters", []))
    for required in (
        "project_id",
        "delivery_submission_id",
        "delivery_review_task_id",
        "return_to",
    ):
        expect(
            required in params,
            "deep_link.parameter_contract",
            f"deep-link parameter missing: {required}",
        )
    expect(
        any("secret" in str(x).lower() for x in manifest.get("url_forbidden_content", [])),
        "deep_link.parameter_contract",
        "URL forbidden-content list does not exclude secrets",
    )

    expect(
        set(manifest.get("breakpoints", [])) == {"1440", "1280", "1024", "768"},
        "responsive.breakpoints",
        "breakpoints != the four frozen values",
    )
    a11y = re.sub(r"[-‑]", " ", read(A11Y).lower())
    for requirement in ("keyboard", "focus trap", "screen reader", "reduced motion", "aria sort"):
        expect(
            requirement in a11y,
            "accessibility.requirements",
            f"accessibility requirement missing: {requirement}",
        )

    expect(
        manifest.get("implementation_authorizations", {}).get("legacy_delivery_package_repurposed")
        is False,
        "legacy.delivery_package_boundary",
        "manifest does not assert the legacy DeliveryPackage is not repurposed",
    )
    expect(
        "legacy_delivery_package_refs" in read(REVIEW) + read(IA),
        "legacy.delivery_package_boundary",
        "legacy reference contract is not documented",
    )

    dual = manifest.get("dual_anchor_model", {})
    expect(
        dual.get("task_is_agent_execution_source_of_truth") is False,
        "dual_anchor.model_present",
        "manifest does not deny Task as the Agent execution source of truth",
    )
    expect(
        "delivery_review_task_id" in str(dual.get("human_review_anchor", "")),
        "dual_anchor.model_present",
        "human review anchor is not delivery_review_task_id",
    )

    overlap = manifest.get("operator_console_overlap", {})
    expect(
        overlap.get("existing_route") == "/operator",
        "operator_console.duplication_analysis",
        "OperatorConsole overlap analysis missing from the manifest",
    )
    expect(
        "Delivery Review" in str(overlap.get("canonical_po_decision_entry_point", "")),
        "operator_console.duplication_analysis",
        "canonical PO decision entry point is not Delivery Review",
    )
    expect(
        bool(overlap.get("fe2_coexistence_gate")),
        "operator_console.duplication_analysis",
        "FE2 coexistence gate is not recorded",
    )
    expect(
        "OperatorReviewPanel" in read(ROUTES_DOC),
        "operator_console.duplication_analysis",
        "route map does not contain the OperatorConsole duplication analysis",
    )

    filters = {f.get("name") for f in manifest.get("inbox_filters", [])}
    expect(
        {"delivery_review_task_status", "delivery_submission_status"} <= filters,
        "inbox.filter_terminology_disambiguated",
        f"inbox filters are not disambiguated; got {sorted(filters)}",
    )
    for entry in manifest.get("inbox_filters", []):
        for field in (
            "source_field",
            "enum_source",
            "display_label",
            "missing_data_behavior",
            "backend_dependency",
        ):
            expect(
                bool(entry.get(field)),
                "inbox.filter_terminology_disambiguated",
                f"inbox filter {entry.get('name')} missing definition field: {field}",
            )
    inbox_text = read(INBOX)
    expect(
        "delivery_review_task_status" in inbox_text and "delivery_submission_status" in inbox_text,
        "inbox.filter_terminology_disambiguated",
        "inbox spec does not use the disambiguated filter names",
    )


def check_no_implementation(manifest: dict) -> None:
    authorizations = manifest.get("implementation_authorizations", {})
    expect(
        authorizations.get("codex_authorized") is False,
        "no_implementation.claims",
        "manifest does not record codex_authorized false",
    )
    expect(
        "NOT GRANTED" in str(authorizations.get("merge_authorization", "")).upper(),
        "no_implementation.claims",
        "manifest does not record merge authorization NOT GRANTED",
    )
    for key in ("frontend_implementation", "backend_implementation"):
        expect(
            "NOT" in str(authorizations.get(key, "")).upper(),
            "no_implementation.claims",
            f"manifest does not record {key} as not started/not authorized",
        )
    expect(
        authorizations.get("task_roles_modified") is False,
        "no_implementation.claims",
        "manifest does not assert TASK_ROLES unmodified",
    )
    expect(
        authorizations.get("adr_66d_09_modified") is False,
        "no_implementation.claims",
        "manifest does not assert ADR-66D-09 unmodified",
    )
    combined = "\n".join(read(p) for p in DOC_FILES).lower()
    expect(
        "no frontend implementation" in combined,
        "no_implementation.claims",
        "design documents do not state 'no frontend implementation'",
    )
    expect(
        manifest.get("production_executed_true_count") == 0,
        "production.executed_count_zero",
        "manifest production_executed_true_count != 0",
    )
    expect(
        "production_executed_true_count: 0" in "\n".join(read(p) for p in DOC_FILES)
        or "production_executed_true_count = 0" in "\n".join(read(p) for p in DOC_FILES),
        "production.executed_count_zero",
        "design documents do not record production_executed_true_count 0",
    )


def check_security() -> None:
    for path in [*DOC_FILES, MANIFEST]:
        text = read(path)
        expect(
            SECRET_SHAPES.search(text) is None,
            "security.no_secret_shapes",
            f"possible secret shape in {path.name}",
        )
        expect(
            LOCAL_PATH_SHAPES.search(text) is None,
            "security.no_local_absolute_paths",
            f"local absolute path committed in {path.name}",
        )


def main() -> int:
    if not MANIFEST.is_file():
        print(f"  [FAIL] manifest.valid_json: missing {MANIFEST.relative_to(ROOT)}")
        print(f"{MARKER}: FAIL")
        return 1
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        parsed_ok = isinstance(manifest, dict)
    except json.JSONDecodeError as exc:
        manifest = {}
        parsed_ok = False
        print(f"  [FAIL] manifest.valid_json: {exc}")
    expect(parsed_ok, "manifest.valid_json", "manifest is not a valid JSON object")

    check_scope()
    check_artifacts()
    check_baseline(manifest)
    check_manifest_shape(manifest)
    check_ia(manifest)
    check_enums(manifest)
    check_states(manifest)
    check_counts(manifest)
    check_route_truthfulness(manifest)
    check_route_truthfulness_across_representations(manifest)
    check_contracts(manifest)
    check_no_implementation(manifest)
    check_security()

    failed_ids = {f.split(":")[0] for f in failures}

    def section(name: str, prefixes: tuple[str, ...]) -> str:
        hit = any(fid.startswith(prefixes) for fid in failed_ids)
        return f"{name}: {'FAIL' if hit else 'PASS'}"

    print(f"  CHECK_DEFINITIONS={CHECK_DEFINITIONS}")
    print(f"  ASSERTIONS_EXECUTED={assertions_executed}")
    print("  " + section("DESIGN_RM1_SCOPE_EXACT", ("scope.", "artifacts.")))
    print("  " + section("DESIGN_RM1_SOURCE_COUNTS", ("counts.",)))
    print("  " + section("DESIGN_RM1_ENUM_INTEGRITY", ("enum.", "states.", "ia.")))
    print("  " + section("DESIGN_RM1_ROUTE_TRUTHFULNESS", ("routes.",)))
    print(
        "  "
        + section(
            "DESIGN_RM1_REGRESSION_CLOSURE",
            ("manifest.", "security.", "no_implementation.", "production."),
        )
    )

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] exact 14-path scope; JSON manifest; exact enums (6/3/9); 7 data states + 6")
    print("       permission states with a populated Activity Timeline unknown cell; route, nav,")
    print("       badge, file and mutation-surface counts re-derived from source and matched;")
    print("       absent routes not implemented; placeholders not functional; QA rerun 1 and")
    print("       backend-authoritative; expiry blocks accept/reject; blocking follow-up rule;")
    print("       identity gate; freshness; deep-link; responsive; a11y; legacy boundary; dual")
    print("       anchor; OperatorConsole duplication analysis; disambiguated inbox filters;")
    print("       no implementation; no secrets or local paths; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
