#!/usr/bin/env python3
"""AT-M1 -- autonomous team architecture reset verifier.

Deterministic and read-only. Confirms that the AT-D01..AT-D05 binding decisions are recorded, that
the canonical entity contracts exist and stay separated (ActorPrincipal vs TASK_ROLES, TeamDecision
vs ProductOwnerDecision), that PlanRevision is versioned and the template planner is not canonical,
that the debug/replan back-edge is contracted, that AT-D09 remains OPEN, that the preserved 66D
boundary is untouched, that PR #28 stays held, and that this stage introduced no implementation.

Positive scope is a fixed baseline plus an explicit path registry compared by SET EQUALITY -- never
a broad positive prefix. It is `AT_M1_BASELINE...HEAD` while the branch is open, which is safe only
because the registry bounds it exactly; the merge stage must freeze the endpoint to the stage head.

Starts no runtime, container, database, migration apply or external provider.

Marker: AT_M1_ARCHITECTURE_RESET_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "AT_M1_ARCHITECTURE_RESET_VERIFY"

# Re-pinned at AT-M1-RM1 (finding A-01). The former baseline 2d4da80 predates the canonical merge
# of GOV1 (PR #30), so GOV1's own paths fell inside AT_M1_BASELINE...HEAD without being AT-M1 stage
# paths. POST_GOV1_CANONICAL_MAIN is the canonical main after that merge and its canonicalization.
AT_M1_BASELINE = "fa5e5c4e6712fbbc59bf18d2ee33421c28f9b009"
AT_M1_BASELINE_SHORT = "fa5e5c4"
AT_M1_POSITIVE_RANGE = f"{AT_M1_BASELINE}...HEAD"

ARCH = "docs/architecture/autonomous-team"
CONTRACTS = "docs/contracts/autonomous-team"
HANDOFF = "docs/handoffs/autonomous-team"

RESET = f"{ARCH}/at-m1-architecture-reset.md"
PRINCIPAL = f"{ARCH}/actor-principal-and-team-model.md"
COLLAB = f"{ARCH}/collaboration-and-workroom-model.md"
PLANNING = f"{ARCH}/planning-and-plan-revision-model.md"
ORCHESTRATION = f"{ARCH}/orchestration-debug-replan-model.md"
LINEAGE = f"{ARCH}/source-of-truth-and-lineage-model.md"
HUMAN = f"{ARCH}/human-intervention-and-governance-boundary.md"
POC = f"{ARCH}/functional-poc-capability-contract.md"
MILESTONES = f"{ARCH}/implementation-milestone-plan.md"

BINDING = f"{CONTRACTS}/at-binding-decisions.md"
TERMINOLOGY = f"{CONTRACTS}/at-canonical-terminology-registry.md"
REGISTRY = f"{CONTRACTS}/at-capability-state-registry.json"

ADRS = "docs/decisions/at-m1-architecture-decisions.md"
EVIDENCE = f"{HANDOFF}/at-m1-evidence.md"
SLICES = f"{HANDOFF}/at-m1-implementation-slice-handoff.md"
VERIFIER = "scripts/verify_at_m1_architecture_reset.py"
TESTS = "tests/test_at_m1_architecture_reset.py"

# Authorized at AT-M1-RM1 (CANONICAL-REGISTRATION-01 / -02): the two EXISTING canonical registries
# the AT family must appear in. No parallel precedence or milestone system is created.
MASTER = "docs/alignment/66-project-completion/master"
PRECEDENCE = f"{MASTER}/canonical-source-of-truth-precedence.md"
MANIFEST = f"{MASTER}/canonical-milestone-manifest.md"

AT_M1_EXPECTED_PATHS = frozenset(
    {
        RESET,
        PRINCIPAL,
        COLLAB,
        PLANNING,
        ORCHESTRATION,
        LINEAGE,
        HUMAN,
        POC,
        MILESTONES,
        BINDING,
        TERMINOLOGY,
        REGISTRY,
        ADRS,
        EVIDENCE,
        SLICES,
        VERIFIER,
        TESTS,
        PRECEDENCE,
        MANIFEST,
    }
)
AT_M1_ORIGINAL_PATH_COUNT = 17
AT_M1_RM1_REGISTRATION_PATHS = (PRECEDENCE, MANIFEST)

ARCHITECTURE_DOCS = (
    RESET,
    PRINCIPAL,
    COLLAB,
    PLANNING,
    ORCHESTRATION,
    LINEAGE,
    HUMAN,
    POC,
    MILESTONES,
)

BINDING_DECISIONS = ("AT-D01", "AT-D02", "AT-D03", "AT-D04", "AT-D05")
ADR_IDS = tuple(f"AT-ADR-{n:02d}" for n in range(1, 9))
MILESTONE_IDS = ("AT-M2", "AT-M3", "AT-M4", "AT-M5", "AT-M6", "AT-M7", "AT-M8")

TEAM_PHASES = (
    "PLANNING",
    "DISCUSSING",
    "READY",
    "EXECUTING",
    "VERIFYING",
    "DEBUGGING",
    "REPLANNING",
    "WAITING_FOR_HUMAN",
    "BLOCKED",
    "DELIVERING",
    "COMPLETED",
    "HALTED",
)

# Canonical TASK_ROLES, read from the live source so the check cannot drift from reality.
RBAC_SOURCE = "shared/sdk/tasks/rbac.py"

# Fields that must never be contracted for. AT-D03 R8 / INV-04.
FORBIDDEN_STORAGE_FIELDS = (
    "private_chain_of_thought",
    "raw_system_prompt",
    "hidden_reasoning",
    "reasoning_tokens",
    "token_trace",
    "private_scratchpad",
    "unredacted_prompt",
)

# INV-04 hardening (AT-M1-RM1). Substrings that make a CONTRACTED FIELD NAME a hidden-reasoning
# leak. Matched against parsed field names only -- never against prose -- so a prohibition list
# that names these can coexist with a contract that must not.
FORBIDDEN_FIELD_NAME_MARKERS = (
    "chain_of_thought",
    "raw_reasoning",
    "hidden_reasoning",
    "reasoning_token",
    "token_trace",
    "scratchpad",
    "system_prompt",
    "unredacted",
    "secret",
)

ALLOWED_CAPABILITY_STATES = (
    "IMPLEMENTED",
    "PARTIAL",
    "MOCK_ONLY",
    "CONTRACT_ONLY",
    "NOT_IMPLEMENTED",
    "DEFERRED",
)

# AT-M1 is documentation only. Any path under these prefixes is an implementation breach.
FORBIDDEN_SCOPE_PREFIXES = (
    "agents/",
    "apps/",
    "shared/",
    "migrations/",
    "infra/",
    "runtime/",
    "helm/",
    "k8s/",
    ".github/",
)

FORBIDDEN_EXACT_PATHS = (
    "source/progress.md",
    "requirements.txt",
    "pyproject.toml",
    RBAC_SOURCE,
)

# Identifier-leak patterns, written as regexes with single-character classes so this scanner does
# not itself contain the literals it forbids -- a scanner exempt from its own check is no scanner.
LEAK_PATTERNS = (
    (r"\b10\.0\.1\.\d{1,3}\b", "internal IPv4 address"),
    (r"aiagent[-]swd", "SSH host alias"),
    (r"\bi[t]admin\b", "internal username"),
    (r"\bstp[a]dmin\b", "internal username"),
    (r"[C]:\\Users\\", "local absolute path"),
    (r"/hom[e]/\w", "local absolute path"),
    (r"post[g]res(?:ql)?://", "database DSN"),
)

failures: list[str] = []
checks_run = 0


def expect(ok: bool, label: str, message: str) -> None:
    global checks_run
    checks_run += 1
    if not ok:
        failures.append(f"{label}: {message}")
        print(f"  [FAIL] {label}: {message}")


def read(relpath: str) -> str:
    path = ROOT / relpath
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def task_roles_from_source() -> set[str]:
    """The canonical TASK_ROLES set, parsed from rbac.py rather than hard-coded here."""
    source = read(RBAC_SOURCE)
    match = re.search(
        r"TASK_ROLES:\s*frozenset\[str\]\s*=\s*frozenset\(\s*\{(.*?)\}", source, re.DOTALL
    )
    if not match:
        return set()
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


def contracted_field_names(doc: str, heading: str) -> tuple[str, ...]:
    """Field names actually CONTRACTED under a heading's first fenced block.

    INV-04 hardening (AT-M1-RM1). The previous check compared a whole-document count against an
    identical whole-document count, so it reduced to "the name appears somewhere" and a contracted
    `private_chain_of_thought` inside the TeamMessage schema passed. Parsing the block into field
    names separates "named in a prohibition list" from "contracted as a member".
    """
    if heading not in doc:
        return ()
    after = doc.split(heading, 1)[1]
    if after.count("```") < 2:
        return ()
    block = after.split("```", 2)[1]
    lines = block.splitlines()
    if lines and lines[0].strip() in ("text", "json", ""):
        lines = lines[1:]
    return tuple(line.split()[0] for line in lines if line.split())


def leaking_field_names(fields: tuple[str, ...]) -> list[str]:
    return sorted(
        field
        for field in fields
        if any(marker in field.lower() for marker in FORBIDDEN_FIELD_NAME_MARKERS)
    )


def labelled_line(doc: str, prefix: str) -> str:
    for line in doc.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()
    return ""


def table_row(doc: str, needle: str) -> str:
    for line in doc.splitlines():
        if line.lstrip().startswith("|") and needle in line:
            return line.strip()
    return ""


def claims_canonical(text: str) -> bool:
    """True if the text asserts canonical status, ignoring the literal NON-CANONICAL denial."""
    return "CANONICAL" in text.upper().replace("NON-CANONICAL", "")


def capability_registry() -> dict:
    try:
        return json.loads(read(REGISTRY))
    except json.JSONDecodeError:
        return {}


def main() -> int:  # noqa: PLR0915
    binding = read(BINDING)
    terminology = read(TERMINOLOGY)
    adrs = read(ADRS)
    principal = read(PRINCIPAL)
    collab = read(COLLAB)
    planning = read(PLANNING)
    orchestration = read(ORCHESTRATION)
    lineage = read(LINEAGE)
    human = read(HUMAN)
    poc = read(POC)
    milestones = read(MILESTONES)
    evidence = read(EVIDENCE)
    slices = read(SLICES)
    registry = capability_registry()

    # --- 1. baseline and exact positive scope ------------------------------------------------
    expect(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", AT_M1_BASELINE, "HEAD"], cwd=ROOT, check=False
        ).returncode
        == 0,
        "check01",
        f"the AT-M1 canonical baseline {AT_M1_BASELINE_SHORT} is not an ancestor of HEAD",
    )
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", AT_M1_POSITIVE_RANGE).splitlines()
        if line.strip()
    }
    expect(
        changed == AT_M1_EXPECTED_PATHS,
        "check02",
        "changed paths are not exactly the AT-M1 registry: "
        f"unexpected={sorted(changed - AT_M1_EXPECTED_PATHS)} "
        f"missing={sorted(AT_M1_EXPECTED_PATHS - changed)}",
    )
    expect(
        len(AT_M1_EXPECTED_PATHS) == 19,
        "check03",
        f"the AT-M1 path registry must hold exactly 19 paths, holds {len(AT_M1_EXPECTED_PATHS)}",
    )
    expect(
        len(AT_M1_EXPECTED_PATHS) - len(AT_M1_RM1_REGISTRATION_PATHS) == AT_M1_ORIGINAL_PATH_COUNT,
        "check03a",
        "the 19-path registry is not exactly the 17 original AT-M1 paths plus the two "
        "RM1-authorized canonical registration paths",
    )
    expect(
        all(path in AT_M1_EXPECTED_PATHS for path in AT_M1_RM1_REGISTRATION_PATHS),
        "check03b",
        "the authorized canonical registration paths are not in the AT-M1 registry",
    )
    gov1_contamination = sorted(
        p for p in changed if "gov1" in p or p.startswith("scripts/verify_step66")
    )
    expect(
        gov1_contamination == [],
        "check03c",
        f"GOV1 paths contaminate the AT-M1 positive scope (A-01 regression): {gov1_contamination}",
    )

    # --- 2. no implementation (INV-10) --------------------------------------------------------
    offenders = sorted(p for p in changed if p.startswith(FORBIDDEN_SCOPE_PREFIXES))
    expect(offenders == [], "check04", f"AT-M1 introduced implementation paths: {offenders}")
    breached = sorted(p for p in changed if p in FORBIDDEN_EXACT_PATHS)
    expect(breached == [], "check05", f"a protected file was modified: {breached}")
    expect(
        "source/progress.md" not in changed,
        "check06",
        "source/progress.md must remain unchanged (ADV-DRIFT-PROGRESS-01)",
    )
    expect(
        not any(p.endswith(".sql") for p in changed),
        "check07",
        "AT-M1 must create no migration",
    )
    expect(
        not any(p.endswith((".tsx", ".ts", ".jsx", ".css")) for p in changed),
        "check08",
        "AT-M1 must create no frontend source",
    )
    expect(
        sorted(p for p in changed if not p.startswith("docs/")) == sorted([VERIFIER, TESTS]),
        "check09",
        "the only non-docs paths may be the AT-M1 verifier and its tests",
    )

    # --- 3. binding decisions AT-D01..D05 present ---------------------------------------------
    for index, decision in enumerate(BINDING_DECISIONS, start=10):
        expect(
            f"## {decision}" in binding and f"{decision}:  RESOLVED / BINDING" in binding,
            f"check{index:02d}",
            f"{decision} is not recorded as RESOLVED / BINDING in the binding decisions contract",
        )
    expect(
        binding.count("RESOLVED / BINDING") >= 5,
        "check15",
        "fewer than five binding decisions are marked RESOLVED / BINDING",
    )
    expect(
        AT_M1_BASELINE in binding,
        "check16",
        "the binding decisions contract does not pin the canonical baseline",
    )

    # --- 4. ADRs ------------------------------------------------------------------------------
    for index, adr in enumerate(ADR_IDS, start=17):
        expect(f"## {adr}" in adrs, f"check{index:02d}", f"{adr} is missing")
    expect(
        adrs.count("**Status:** ACCEPTED") == 8,
        "check25",
        "exactly eight ADRs must be recorded as ACCEPTED",
    )

    # --- 5. AT-D01 execution source of truth (INV-02) -----------------------------------------
    expect(
        "SOLE" in flat(binding).upper() and "Goal" in binding and "Work Item" in binding,
        "check26",
        "AT-D01 does not assert a sole execution lineage",
    )
    expect(
        "MUST NOT become a second autonomous execution lineage" in flat(binding),
        "check27",
        "AT-D01 does not forbid a second autonomous execution lineage",
    )
    expect(
        "SUBORDINATE HUMAN INTERACTION SURFACE" in lineage,
        "check28",
        "the lineage model does not subordinate /tasks",
    )
    expect(
        "TWO EXECUTION SYSTEMS" in lineage and "FORBIDDEN" in lineage,
        "check29",
        "the lineage model does not name the forbidden two-pipeline outcome",
    )

    # --- 6. AT-D02 principal separation (INV-01) ----------------------------------------------
    roles = task_roles_from_source()
    expect(
        roles
        == {
            "requester",
            "pm_engineering_lead",
            "reviewer_approver",
            "platform_admin",
            "agent_operator",
            "security_compliance_reviewer",
        },
        "check30",
        f"TASK_ROLES has changed: {sorted(roles)}",
    )
    expect(
        not any(bad in roles for bad in ("runtime_agent", "ai_partner", "agent", "system")),
        "check31",
        "TASK_ROLES contains a non-human principal type (INV-01)",
    )
    for index, term in enumerate(("human", "runtime_agent", "ai_partner", "system"), start=32):
        expect(term in principal, f"check{index:02d}", f"principal type {term!r} is not contracted")
    expect(
        "MUST NOT be added to TASK_ROLES" in flat(binding),
        "check36",
        "AT-D02 does not forbid adding agents to TASK_ROLES",
    )
    expect(
        "LOGICAL principal" in principal
        and "does NOT imply an authenticated production identity" in flat(principal),
        "check37",
        "the principal model does not state the authentication boundary",
    )

    # --- 7. AT-D03 collaboration and the storage prohibition (INV-04) -------------------------
    for index, field in enumerate(FORBIDDEN_STORAGE_FIELDS, start=38):
        # The prohibition itself must still be stated somewhere in the architecture contracts.
        occurrences = sum(doc.count(field) for doc in (collab, binding, orchestration))
        expect(
            occurrences > 0,
            f"check{index:02d}",
            f"{field!r} is no longer named in any prohibition list",
        )
    # INV-04 behavioral gate (AT-M1-RM1): parse the ACTUAL TeamMessage contract and prove no
    # contracted member is a hidden-reasoning field. The prohibition prose above cannot satisfy
    # this, and a contracted field cannot hide behind it.
    team_message_fields = contracted_field_names(collab, "## 4. TeamMessage")
    expect(
        len(team_message_fields) >= 10,
        "check45a",
        "the TeamMessage contract block could not be parsed -- INV-04 cannot be enforced "
        f"(parsed {len(team_message_fields)} fields)",
    )
    expect(
        "sender_principal_id" in team_message_fields and "thread_id" in team_message_fields,
        "check45b",
        f"the parsed TeamMessage block is not the real contract: {team_message_fields[:6]}",
    )
    leaks = leaking_field_names(team_message_fields)
    expect(
        leaks == [],
        "check45c",
        f"TeamMessage CONTRACTS hidden-reasoning fields (INV-04 violation): {leaks}",
    )
    for entity, label in (
        ("## 5. Message types", "check45d"),
        ("## 6. ConversationThread", "check45e"),
    ):
        entity_leaks = leaking_field_names(contracted_field_names(collab, entity))
        expect(
            entity_leaks == [],
            label,
            f"{entity} contracts hidden-reasoning fields: {entity_leaks}",
        )
    expect(
        "FORBIDDEN FIELDS" in collab,
        "check45",
        "the collaboration model does not declare a forbidden-field list",
    )
    for index, semantic in enumerate(
        (
            "thread",
            "recipient",
            "reply",
            "proposal",
            "challenge",
            "handoff",
            "blocker",
            "clarification",
            "debug_hypothesis",
            "debug_result",
            "replan",
        ),
        start=46,
    ):
        expect(
            semantic in collab.lower(),
            f"check{index:02d}",
            f"collaboration semantic {semantic!r} is not contracted",
        )
    expect(
        "recipient_principal_id" in collab and "parent_message_id" in collab,
        "check57",
        "TeamMessage lacks addressing or threading fields",
    )

    # --- 8. TeamDecision separation (INV-03) --------------------------------------------------
    expect(
        "MUST NOT share enums" in flat(collab) or "MUST NOT share enums" in flat(human),
        "check58",
        "the three decision types are not declared enum-separate",
    )
    expect(
        "does NOT authorize a production action" in flat(collab),
        "check59",
        "TeamDecision is not barred from authorizing production actions",
    )
    expect(
        "does NOT replace human approval" in flat(collab)
        and "does NOT replace Product Owner acceptance" in flat(collab),
        "check60",
        "TeamDecision is not barred from replacing approval or PO acceptance",
    )
    expect(
        "options_considered" in collab and "dissent_summary" in collab,
        "check61",
        "TeamDecision lacks options_considered or dissent_summary",
    )

    # --- 9. PlanRevision (INV-05) and template demotion (INV-07) ------------------------------
    for index, prop in enumerate(
        ("VERSIONED", "HISTORICALLY IMMUTABLE", "SUPERSEDABLE", "DIFFABLE", "TRACEABLE"), start=62
    ):
        expect(prop in planning, f"check{index:02d}", f"PlanRevision property {prop!r} is missing")
    expect(
        "supersedes_revision_id" in planning and "revision_number" in planning,
        "check67",
        "PlanRevision lacks versioning or supersession fields",
    )
    expect(
        "Mutable-history overwrite is FORBIDDEN" in planning,
        "check68",
        "PlanRevision does not forbid mutable-history overwrite",
    )
    expect(
        "TEST / DEMO FIXTURE ONLY" in planning and "task_graph.py" in planning,
        "check69",
        "the template planner is not explicitly demoted to a fixture (INV-07)",
    )
    expect(
        "Canonical?        NO" in planning,
        "check70",
        "the template planner is not explicitly marked non-canonical",
    )

    # --- 10. loop / back-edge (INV-06) --------------------------------------------------------
    for index, phase in enumerate(TEAM_PHASES, start=71):
        expect(phase in orchestration, f"check{index:02d}", f"team phase {phase!r} is missing")
    expect(
        "VERIFYING  --failure-->        DEBUGGING" in orchestration
        or ("VERIFYING" in orchestration and "-> DEBUGGING" in orchestration),
        "check83",
        "the VERIFYING -> DEBUGGING back-edge is missing",
    )
    expect(
        "DEBUGGING  -> REPLANNING" in orchestration
        or "DEBUGGING    -> REPLANNING" in orchestration,
        "check84",
        "the DEBUGGING -> REPLANNING back-edge is missing",
    )
    expect(
        "REPLANNING   -> READY" in orchestration or "REPLANNING -> READY" in orchestration,
        "check85",
        "the REPLANNING -> READY back-edge is missing",
    )
    expect(
        "DLQ is a reliability mechanism" in flat(orchestration)
        and "NOT an autonomous debugging model" in flat(orchestration),
        "check86",
        "retry and debug are not separated (INV-06)",
    )
    expect(
        "attempt_number" in orchestration and "budget" in orchestration.lower(),
        "check87",
        "DebugAttempt lacks attempt numbering or a budget contract",
    )
    expect(
        "termination" in orchestration.lower() and "no progress" in orchestration.lower(),
        "check88",
        "loop termination or the no-progress rule is missing",
    )
    expect(
        "DIFFERENT DOMAINS" in orchestration and "DeliverySubmission" in orchestration,
        "check89",
        "team phase and DeliverySubmission status are not domain-separated",
    )

    # --- 11. dynamic dispatch demotion --------------------------------------------------------
    expect(
        "DEMOTED" in orchestration and "work-item-dispatch-policy.yaml" in orchestration,
        "check90",
        "static YAML dispatch is not demoted",
    )
    expect(
        "forbidden as the autonomous source of truth" in flat(orchestration),
        "check91",
        "the YAML map is not forbidden as the autonomous source of truth",
    )

    # --- 12. AT-D09 remains OPEN --------------------------------------------------------------
    expect(
        "AT-D09" in binding and "OPEN" in binding,
        "check92",
        "AT-D09 is not recorded",
    )
    expect(
        "DEFERRED" in binding and "must not canonicalize permissive continuation" in flat(binding),
        "check93",
        "AT-D09 does not remain deferred, or permissive continuation was canonicalized",
    )
    expect(
        "AT-D09" not in adrs.split("## Open decisions")[0],
        "check94",
        "AT-D09 must not be recorded as a closed ADR",
    )
    expect(
        "REMAINS AUTHORITATIVE" in binding,
        "check95",
        "the existing clarification expiry contract is not preserved as authoritative",
    )

    # --- 13. 66D preserved boundary (INV-09) --------------------------------------------------
    for index, preserved in enumerate(
        ("Delivery Review", "Review Gate Actions", "ProductOwnerDecision"), start=96
    ):
        expect(
            preserved in binding,
            f"check{index:02d}",
            f"the preserved 66D item {preserved!r} is not listed",
        )
    expect(
        "preserved" in binding.lower() and all(f"66D-D0{n}" in binding for n in range(1, 6)),
        "check99",
        "the 66D binding decisions 66D-D01..D05 are not all declared preserved",
    )
    expect(
        "VERSIONED amendment" in binding or "versioned amendment" in binding,
        "check100",
        "the 66D amendment is not declared versioned (no edit-in-place)",
    )

    # --- 14. PR #28 hold (INV-08) -------------------------------------------------------------
    # INV-08 structural gate (AT-M1-RM1). The previous checks searched the WHOLE file for "HOLD"
    # and "NON-CANONICAL", so PR #28 could be declared CANONICAL / ACTIVE / MERGE-READY on its own
    # treatment line while incidental text elsewhere kept both checks green. These target the
    # authoritative treatment line and the canonical-input-registry row for PR #28 specifically.
    treatment = labelled_line(evidence, "PR #28 treatment:")
    expect(
        treatment != "",
        "check101",
        "the evidence has no authoritative 'PR #28 treatment:' line",
    )
    expect(
        "HOLD" in treatment.upper() and "PRESERVE" in treatment.upper(),
        "check101a",
        f"the PR #28 treatment line does not state HOLD / PRESERVE: {treatment!r}",
    )
    expect(
        "NON-CANONICAL" in treatment.upper(),
        "check102",
        f"the PR #28 treatment line does not state NON-CANONICAL: {treatment!r}",
    )
    expect(
        not claims_canonical(treatment),
        "check102a",
        f"the PR #28 treatment line asserts canonical status: {treatment!r}",
    )
    forbidden_claims = sorted(
        claim
        for claim in ("MERGE-READY", "MERGE READY", "ACTIVE", "DEPENDENCY", "ADOPTED", "MERGED")
        if claim in treatment.upper().replace("NOT MERGED", "")
    )
    expect(
        forbidden_claims == [],
        "check102b",
        f"the PR #28 treatment line claims active/merge-ready status {forbidden_claims}: "
        f"{treatment!r}",
    )
    pr28_row = table_row(evidence, "PR #28")
    expect(
        pr28_row != "" and "hold" in pr28_row.lower(),
        "check102c",
        f"the canonical input registry row for PR #28 does not record a hold: {pr28_row!r}",
    )
    expect(
        "AT-M7" in pr28_row,
        "check102d",
        f"the PR #28 registry row does not defer it to AT-M7: {pr28_row!r}",
    )
    expect(
        not claims_canonical(pr28_row),
        "check102e",
        f"the PR #28 registry row asserts canonical status: {pr28_row!r}",
    )
    expect(
        "HOLD / PRESERVE / NON-CANONICAL" in binding or "HOLD" in binding,
        "check103",
        "the binding decisions do not record the PR #28 hold",
    )
    expect(
        not any("delivery_acceptance" in p or p.startswith("migrations/036") for p in changed),
        "check104",
        "AT-M1 must not touch PR #28 content",
    )

    # --- 14a. canonical registration (AT-M1-RM1) -----------------------------------------------
    precedence = read(PRECEDENCE)
    manifest = read(MANIFEST)
    expect(
        "Autonomous Team architecture precedence" in precedence,
        "check104a",
        "the AT family is not registered in the canonical source-of-truth precedence record",
    )
    for decision in BINDING_DECISIONS:
        expect(
            decision in precedence,
            f"check104a-{decision.lower()}",
            f"{decision} is not registered in the canonical precedence record",
        )
    for label, preserved in (
        ("check104b", "Review Gate Actions"),
        ("check104c", "ProductOwnerDecision"),
        ("check104d", "TASK_ROLES"),
        ("check104e", "D-1"),
    ):
        expect(
            preserved in precedence,
            label,
            f"the precedence record does not preserve {preserved!r} against the AT family",
        )
    expect(
        "scoped precedence, not a global supersession" in flat(precedence),
        "check104f",
        "the precedence record does not scope the AT family -- it must not globally supersede "
        "Step 66 / 66D architecture",
    )
    expect(
        "AT-D09" in precedence and "OPEN" in precedence,
        "check104g",
        "the precedence record does not keep AT-D09 OPEN / DEFERRED",
    )
    expect(
        "Autonomous Team milestones" in manifest,
        "check104h",
        "the AT family is not registered in the canonical milestone manifest",
    )
    for index, milestone in enumerate(
        ("AT-M0", "AT-M1", "AT-M2", "AT-M3", "AT-M4", "AT-M5", "AT-M6", "AT-M7", "AT-M8"),
        start=1,
    ):
        expect(
            milestone in manifest,
            f"check104i-{index}",
            f"{milestone} is not registered in the canonical milestone manifest",
        )
    flat_manifest = flat(manifest)
    for label, milestone in (
        ("check104j", "AT-M2"),
        ("check104k", "AT-M3"),
        ("check104l", "AT-M4"),
        ("check104m", "AT-M5"),
        ("check104n", "AT-M6"),
    ):
        section = flat_manifest.split(milestone, 1)[1][:200] if milestone in flat_manifest else ""
        expect(
            "NOT AUTHORIZED" in section,
            label,
            f"{milestone} is not registered as NOT AUTHORIZED in the milestone manifest",
        )
    expect(
        "PENDING CANONICAL MERGE" in flat_manifest.upper(),
        "check104o",
        "the milestone manifest claims AT-M1 is canonical before PR #29 merges",
    )
    expect(
        not claims_canonical(table_row(manifest, "AT-M7") or "")
        and "AT-M7" in manifest
        and "PR #28" in manifest,
        "check104p",
        "the milestone manifest does not record PR #28 as an AT-M7 input under hold",
    )

    # --- 15. POC contract ---------------------------------------------------------------------
    for index, clause in enumerate(("P01", "P06", "P07", "P12", "P14", "P17", "P18"), start=105):
        expect(clause in poc, f"check{index:02d}", f"POC clause {clause} is missing")
    expect(
        "INVALIDATES the POC run" in poc,
        "check112",
        "the POC contract does not invalidate runs with extra human actions",
    )
    expect(
        all(marker in poc for marker in ("B1", "B2", "B3", "B4", "B5")),
        "check113",
        "the minimum blocking capability set B1..B5 is not recorded",
    )

    # --- 16. milestones -----------------------------------------------------------------------
    for index, milestone in enumerate(MILESTONE_IDS, start=114):
        expect(
            f"{milestone} —" in milestones or f"{milestone} --" in milestones,
            f"check{index:02d}",
            f"milestone {milestone} is missing",
        )
    expect(
        milestones.count("Authorization   NOT AUTHORIZED") >= 7,
        "check121",
        "not every milestone is marked NOT AUTHORIZED",
    )
    expect(
        "POC-BLOCKING" in milestones and "PRODUCTION-BLOCKING" in milestones,
        "check122",
        "the dependency graph is not classified",
    )

    # --- 17. capability registry --------------------------------------------------------------
    caps = registry.get("capabilities", [])
    expect(bool(caps), "check123", "the capability registry has no entries")
    expect(
        all(c.get("state") in ALLOWED_CAPABILITY_STATES for c in caps),
        "check124",
        "a capability uses a state outside the allowed six",
    )
    declared = registry.get("totals", {})
    computed = {
        state: sum(1 for c in caps if c.get("state") == state)
        for state in ALLOWED_CAPABILITY_STATES
    }
    computed["entries"] = len(caps)
    computed["poc_blocking"] = sum(1 for c in caps if c.get("poc_blocking"))
    expect(
        declared == computed,
        "check125",
        f"registry totals disagree with the entries: declared={declared} computed={computed}",
    )
    expect(
        all(c.get("evidence") for c in caps),
        "check126",
        "a capability entry carries no evidence",
    )
    required_caps = {
        "Goal",
        "Team",
        "AgentPrincipal",
        "Discussion",
        "Proposal",
        "Decision",
        "Planning",
        "PlanRevision",
        "Assignment",
        "Delegation",
        "Handoff",
        "Execution",
        "QA",
        "Diagnosis",
        "Debug",
        "Replan",
        "Delivery",
        "Acceptance",
        "Identity",
        "SharedContext",
    }
    present = {c.get("capability") for c in caps}
    expect(
        required_caps <= present,
        "check127",
        f"capability registry is missing required entries: {sorted(required_caps - present)}",
    )
    expect(
        registry.get("canonical_baseline") == AT_M1_BASELINE,
        "check128",
        "the capability registry does not pin the canonical baseline",
    )

    # --- 18. human intervention boundary ------------------------------------------------------
    for index, action in enumerate(
        ("Set goal", "Answer clarification", "Halt", "Accept / reject delivery"), start=129
    ):
        expect(action in human, f"check{index:02d}", f"human action {action!r} is not contracted")
    expect(
        "Assign an agent to work" in human and "**NO**" in human,
        "check133",
        "manual assignment is not excluded from the normal flow",
    )
    expect(
        "MUST NOT   hold a TASK_ROLES role" in human or "hold a TASK_ROLES role" in human,
        "check134",
        "the agent authority ceiling is not contracted",
    )

    # --- 19. terminology consistency ----------------------------------------------------------
    for index, term in enumerate(
        (
            "ActorPrincipal",
            "AgentProfile",
            "ProjectTeamMembership",
            "ConversationThread",
            "TeamMessage",
            "TeamDecision",
            "PlanRevision",
            "Handoff",
            "DebugAttempt",
            "Goal",
        ),
        start=135,
    ):
        expect(
            f"## {term}" in terminology,
            f"check{index:02d}",
            f"terminology registry lacks an entry for {term}",
        )
    expect(
        "CONTRACT_ONLY" in terminology,
        "check145",
        "the terminology registry does not mark terms as contract-only",
    )

    # --- 20. cross-document consistency -------------------------------------------------------
    for index, doc in enumerate(ARCHITECTURE_DOCS, start=146):
        expect(
            "production_executed_true_count: 0" in doc_text(doc),
            f"check{index:02d}",
            f"{doc} does not declare production_executed_true_count: 0",
        )
    expect(
        all("staging-safety:" in doc_text(d) for d in AT_M1_EXPECTED_PATHS if d.endswith(".md")),
        "check155",
        "a markdown artifact is missing the staging-safety footer",
    )
    expect(
        AT_M1_BASELINE_SHORT in evidence or AT_M1_BASELINE in evidence,
        "check156",
        "the evidence does not pin the canonical baseline",
    )
    expect(
        "AT-M2" in slices and "NOT started" in slices,
        "check157",
        "the slice handoff does not record that AT-M2 has not started",
    )

    # --- 21. identifier leak scan (self-inclusive) --------------------------------------------
    scanned = "\n".join(read(path) for path in sorted(AT_M1_EXPECTED_PATHS))
    for index, (pattern, label) in enumerate(LEAK_PATTERNS, start=158):
        expect(
            re.search(pattern, scanned) is None,
            f"check{index:02d}",
            f"an AT-M1 file leaks a {label}",
        )

    print(f"{MARKER}: checks={checks_run} failures={len(failures)}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"{MARKER}: PASS")
    return 0


def doc_text(relpath: str) -> str:
    return read(relpath)


if __name__ == "__main__":
    sys.exit(main())
