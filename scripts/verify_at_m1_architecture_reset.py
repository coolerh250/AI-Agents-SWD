#!/usr/bin/env python3
"""AT-M1 -- autonomous team architecture reset verifier.

Deterministic and read-only. Confirms that the AT-D01..AT-D05 binding decisions are recorded, that
the canonical entity contracts exist and stay separated (ActorPrincipal vs TASK_ROLES, TeamDecision
vs ProductOwnerDecision), that PlanRevision is versioned and the template planner is not canonical,
that the debug/replan back-edge is contracted, that AT-D09 remains OPEN, that the preserved 66D
boundary is untouched, that PR #28 stays held, and that this stage introduced no implementation.

Positive scope is a fixed baseline plus an explicit path registry compared by SET EQUALITY -- never
a broad positive prefix. Since AT-M1-M1 the two scopes are SEPARATE concepts:

  AT_M1_POSITIVE_RANGE  BASELINE...STAGE_HEAD  frozen; what was reviewed and accepted
  AT_M1_CURRENT_RANGE   BASELINE...HEAD        live; what exists now, for rejection logic

Freezing both would let a forbidden path added after the stage head go unseen; freezing neither
would let canonicalization commits break the reviewed-scope proof. Each range answers exactly one
question and they are never interchanged.

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

# Frozen at AT-M1-M1: the exact implementation state independently reviewed at AT-M1-R8 and
# authorized for merge. Canonicalization commits land after it, so the reviewed-scope proof must
# not move with HEAD.
AT_M1_STAGE_HEAD = "c80350ecc19e28212d9a95cddeb80a24aabe6eae"
AT_M1_STAGE_HEAD_SHORT = "c80350e"
# The canonical merge of PR #29. Its SECOND parent is the reviewed stage head, which pins the
# constant above topologically: repointing it -- forward to the merge commit included -- stops
# matching the merge's parentage and fails check01c.
AT_M1_MERGE_COMMIT = "db4e7a781dcddf4f5ab4ac413457a88bc7bdefa0"
AT_M1_MERGE_COMMIT_SHORT = "db4e7a7"

# What was reviewed. Never HEAD-relative.
AT_M1_POSITIVE_RANGE = f"{AT_M1_BASELINE}...{AT_M1_STAGE_HEAD}"
# What exists now. Never frozen -- a forbidden path added after the stage head must still be seen.
AT_M1_CURRENT_RANGE = f"{AT_M1_BASELINE}...HEAD"

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


def changed_paths(range_spec: str) -> set[str]:
    """Repository-relative paths changed over `range_spec`, slash-normalised."""
    return {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", range_spec).splitlines()
        if line.strip()
    }


def forbidden_scope_offenders(paths: set[str]) -> list[str]:
    """Implementation paths AT-M1 may never introduce. Callers must pass the CURRENT set."""
    return sorted(p for p in paths if p.startswith(FORBIDDEN_SCOPE_PREFIXES))


def protected_breaches(paths: set[str]) -> list[str]:
    """Frozen contract files that may never be modified. Callers must pass the CURRENT set."""
    return sorted(p for p in paths if p in FORBIDDEN_EXACT_PATHS)


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


def line_with(doc: str, needle: str) -> str:
    """The first line mentioning needle. Targets a statement instead of the whole document."""
    for line in doc.splitlines():
        if needle in line:
            return line.strip()
    return ""


def section_text(doc: str, heading_prefix: str) -> str:
    """The body of one '## ...' section, so a check cannot be satisfied from another section."""
    lines = doc.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(heading_prefix):
            body: list[str] = []
            for following in lines[index + 1 :]:
                if following.startswith("## "):
                    break
                body.append(following)
            return "\n".join(body)
    return ""


def indented_value(block: str, label: str) -> str:
    """The indented value under a 'Label:' line, e.g. 'Decision:' followed by '    DEFERRED'."""
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == label:
            for following in lines[index + 1 :]:
                if following.strip():
                    return following.strip()
            return ""
    return ""


# =================================================================================================
# Authoritative state semantics (AT-M1-RM5)
#
# RM4 asked "does this text contain a forbidden word?". That is unclosable: every new synonym is a
# new escape (DEF-R5-03), deleting negators to avoid false positives makes "NO LONGER OPEN" read as
# OPEN (DEF-R5-02), and a token test cannot tell "NOT BINDING" from "BINDING" (DEF-R5-07).
#
# RM5 asks instead: what does this assertion CURRENTLY claim, and is that claim one of the states
# this kind of assertion is ALLOWED to hold? Unknown or unparseable authoritative values fail
# closed, so an unseen synonym is rejected without ever being enumerated.
# =================================================================================================

AT_D09_OPEN_TERMS = ("OPEN", "DEFERRED", "UNDECIDED", "PENDING")
# Not the basis of correctness -- acceptance is affirmative. These only let the parser recognise a
# word as a STATE word, so that negation can be attributed to it, and sharpen prose detection.
AT_D09_CLOSURE_TERMS = (
    "RESOLVED",
    "CLOSED",
    "BINDING",
    "ACCEPTED",
    "ANSWERED",
    "AUTHORIZED",
    "DECIDED",
    "COMPLETE",
    "COMPLETED",
    "SUPERSEDED",
    "SUPERSEDES",
    "SETTLED",
    "FINALIZED",
    "FINALISED",
    "RATIFIED",
    "APPROVED",
    "FINAL",
)
AT_AUTHORITY_TERMS = ("AUTHORITATIVE",)
AT_STATE_TERMS = (*AT_D09_OPEN_TERMS, *AT_D09_CLOSURE_TERMS, *AT_AUTHORITY_TERMS)

# Retained names for the nominated-surface checks 92a-92i.
AT_D09_CLOSURE_CLAIMS = AT_D09_CLOSURE_TERMS
AT_D09_OPEN_CLAIMS = AT_D09_OPEN_TERMS
AT_D09_STATE_TOKENS = AT_STATE_TERMS

NEGATORS = ("NO LONGER", "NOT", "NEVER", "NO")
MODALS = ("MAY", "MIGHT", "COULD", "WOULD", "SHOULD", "WILL", "CAN", "SHALL")
HISTORICAL = ("PREVIOUSLY", "FORMERLY", "HISTORICALLY", "ONCE", "EARLIER")

# Anti-vacuity floors. NOT a completeness proof -- the semantic verdict is. These exist so that a
# disabled extractor fails loudly instead of making the real guard vacuously true.
AT_D09_MINIMUM_KNOWN_SURFACES = 24
AT_M2_KNOWN_REGISTERS = 2

# A qualified key is part of the identifier: AT_D09_STATUS is an AT-D09 surface. A plain \b cannot
# see it, because the trailing underscore is itself a word character (DEF-R5-04).
AT_D09_IDENT = re.compile(r"\bAT[-_]D09(?:[_-][A-Za-z0-9]+)*\b", re.IGNORECASE)
AT_M2_IDENT = re.compile(r"\bAT[-_]M2(?:[_-][A-Za-z0-9]+)*\b", re.IGNORECASE)
# A register key may be qualified: AT_D09_STATUS, AT-D09 authorization state, AT_M2 authorization.
AT_D09_REGISTER = re.compile(
    r"(AT[-_]D09(?:[_-][A-Za-z0-9]+)*)((?:\s*\([^)]*\))?[^:\n]{0,48}?):\s*(.*)$", re.IGNORECASE
)
AT_M2_REGISTER = re.compile(
    r"(AT[-_]M2(?:[_-][A-Za-z0-9]+)*)((?:\s*\([^)]*\))?[^:\n]{0,48}?):\s*(.*)$", re.IGNORECASE
)
LABEL_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /_'-]*):\s*(.*)$")

KIND_KEYWORDS = (
    ("decision", ("DECISION",)),
    ("authority", ("AUTHORITY", "GOVERNING")),
    ("authorization", ("AUTHORIZATION", "AUTHORIZED")),
    ("status", ("STATUS", "STATE", "FINAL")),
)


def tokens_in(value: str, vocabulary: tuple[str, ...]) -> list[str]:
    upper = value.upper()
    return sorted({t for t in vocabulary if re.search(rf"\b{t}\b", upper)})


def current_value(value: str) -> str:
    """The CURRENTLY asserted part of an authoritative field.

    A trailing '--' or ';' clause qualifies; a parenthetical qualifies UNLESS it is the only
    content. 'AUTHORIZED (previously NOT AUTHORIZED)' therefore reads as AUTHORIZED, while
    'AT-D09 (OPEN)' reads as OPEN.
    """
    head = re.split(r"\s+--\s+|\s*;\s*", value.strip(), maxsplit=1)[0].strip()
    outside = re.sub(r"\([^)]*\)", " ", head).strip(" \t.,:")
    inside = " ".join(re.findall(r"\(([^)]*)\)", head)).strip()
    if tokens_in(outside, AT_STATE_TERMS):
        return outside
    # The state may be carried by the parenthetical itself: "AT-D09 (OPEN)", "... semantics (OPEN)".
    if tokens_in(inside, AT_STATE_TERMS):
        return inside
    return outside or inside


def propositions(value: str) -> list[tuple[bool, str]]:
    """(affirmed, TERM) for each state term, with negation PRESERVED rather than deleted.

    'NO LONGER OPEN' yields (False, OPEN) -- a closure of an open state. The RM4 form deleted
    'NO LONGER' and read the residue as OPEN (DEF-R5-02).
    """
    found: list[tuple[bool, str]] = []
    for clause in re.split(r"\s*/\s*|\s*,\s*|\s+AND\s+", value.upper()):
        clause = clause.strip()
        if not clause:
            continue
        negated = any(re.search(rf"\b{negator}\b", clause) for negator in NEGATORS)
        for term in AT_STATE_TERMS:
            if re.search(rf"\b{term}\b", clause):
                found.append((not negated, term))
    return found


def is_hypothetical(text: str) -> bool:
    """Modal or historical framing discusses a state; it does not assert one."""
    upper = text.upper()
    return any(re.search(rf"\b{word}\b", upper) for word in (*MODALS, *HISTORICAL))


def asserted_false(value: str) -> bool:
    """A trailing '-- FALSE' is the predicate, not a qualifier.

    The prohibited-implications block states claims in the form '<claim> -- FALSE'. Dropping that
    clause as a qualifier would read 'AT-M2 is authorized -- FALSE' as an affirmation.
    """
    tail = re.split(r"\s+--\s+|\s*;\s*", value.strip(), maxsplit=1)
    return len(tail) > 1 and bool(re.search(r"\bFALSE\b", tail[1], re.IGNORECASE))


def without_code_spans(text: str) -> str:
    """Backticked text is a quotation of a literal, not an assertion about the subject."""
    return re.sub(r"`[^`]*`", " ", text)


def normalized_key(key: str) -> str:
    """Separators become spaces so AT_D09_STATUS exposes STATUS to word-boundary matching."""
    return re.sub(r"[_-]+", " ", key).upper()


def key_is_stateful(key: str) -> bool:
    upper = normalized_key(key)
    return any(re.search(rf"\b{w}\b", upper) for _, words in KIND_KEYWORDS for w in words)


def assertion_kind(key: str, form: str, props: list[tuple[bool, str]], subject: str) -> str:
    if subject == "at-m2":
        return "at-m2-authorization"
    upper = normalized_key(key)
    for kind, words in KIND_KEYWORDS:
        if any(re.search(rf"\b{w}\b", upper) for w in words):
            return kind
    affirmed = {term for affirm, term in props if affirm}
    # A value whose only affirmation is AUTHORITATIVE is a governing-authority statement, whatever
    # its label: "Current canonical implementation: ... REMAINS AUTHORITATIVE".
    if affirmed & set(AT_AUTHORITY_TERMS) and not affirmed & set(AT_D09_OPEN_TERMS):
        return "authority"
    if form in ("prose", "block-entry", "table-cell") and props and not affirmed:
        return "non-decision"
    return "status"


def state_verdict(kind: str, props: list[tuple[bool, str]]) -> str:
    """'' when the current value is an ALLOWED state for this kind, else why it is not.

    Acceptance is affirmative and fails closed: an authoritative value that does not affirm a
    canonical allowed state is rejected without the offending term being pre-enumerated.
    """
    affirmed = {term for affirm, term in props if affirm}
    negated = {term for affirm, term in props if not affirm}
    closure = set(AT_D09_CLOSURE_TERMS)
    openish = set(AT_D09_OPEN_TERMS)

    if kind == "at-m2-authorization":
        if "AUTHORIZED" in affirmed:
            return "current state is AUTHORIZED"
        if "AUTHORIZED" in negated:
            return ""
        return "AT-M2 authorization is not affirmatively NOT AUTHORIZED"
    if kind == "authority":
        if affirmed & {"SUPERSEDED", "SUPERSEDES"}:
            return "governing authority claimed superseded"
        if "AUTHORITATIVE" in affirmed:
            return ""
        if affirmed & closure:
            return f"affirms closure state {sorted(affirmed & closure)}"
        return "governing authority is not affirmed AUTHORITATIVE"
    if kind == "non-decision":
        if affirmed & closure:
            return f"affirms closure state {sorted(affirmed & closure)}"
        return ""
    if kind == "decision":
        if affirmed & closure:
            return f"affirms closure state {sorted(affirmed & closure)}"
        if "DEFERRED" in affirmed or negated & {"DECIDED"}:
            return ""
        return "decision value is neither DEFERRED nor an explicit non-decision"
    if kind == "authorization":
        # Allowed: no decision and no authorization to close.
        if affirmed & closure:
            return f"affirms closure state {sorted(affirmed & closure)}"
        if negated & {"AUTHORIZED", "DECIDED"} or affirmed & openish:
            return ""
        if negated & openish:
            return f"negates the open state {sorted(negated & openish)}"
        return "no canonical open state is affirmed (unknown authoritative value)"
    if affirmed & closure:
        return f"affirms closure state {sorted(affirmed & closure)}"
    if negated & openish:
        return f"negates the open state {sorted(negated & openish)}"
    if affirmed & openish:
        return ""
    return "no canonical open state is affirmed (unknown authoritative value)"


# =================================================================================================
# Canonical state carrier protocol (AT-D10, implemented at AT-M1-RM6)
#
# AT-D10 makes STRUCTURED CARRIERS the sole canonical authority for governance state. Free prose
# explains, quotes, criticises and speculates, but never creates, closes or authorizes state.
#
# The ordering matters and is the whole point of this stage:
#
#     DISCOVERY (structural)  ->  KIND (from the carrier's key)  ->  VALUE  ->  VALIDATION
#
# RM5 discovered a carrier only if its value or its key already contained an enumerated word, so a
# register with an unforeseen key AND an unforeseen value was never judged at all (R6-B1). Here a
# subject-keyed field in a canonical artifact IS a carrier, whatever it is called and whatever it
# says, and an uninterpretable value FAILS CLOSED.
# =================================================================================================

# Canonical state artifacts. Derived from the precedence contract, which makes the binding
# decisions contract Tier 1 and lists no handoff or evidence record as an authority. The evidence
# and slice handoffs are stage records and forward inputs: they may quote, tabulate and narrate
# canonical state -- including reproducing register syntax -- without ever binding it.
NON_CANONICAL_STATE_ARTIFACTS = (EVIDENCE, SLICES)

SUBJECT_PATTERNS = {
    "at-d09": re.compile(r"AT[-_]D09[A-Za-z0-9_.-]*", re.IGNORECASE),
    "at-m2": re.compile(r"AT[-_]M2[A-Za-z0-9_.-]*", re.IGNORECASE),
}
# A carrier key BEGINS with the subject identifier. What follows it, up to the colon, is the
# qualifier and is accepted unconditionally -- see keyed_field().
SUBJECT_KEY_START = {
    subject: re.compile(rf"^{pattern.pattern}", re.IGNORECASE)
    for subject, pattern in SUBJECT_PATTERNS.items()
}

# Markdown decoration is formatting, not grammar. Removing it first makes "- AT-D09: ...",
# "> AT-D09: ..." and "**AT-D09:** ..." the same carrier as "AT-D09: ...".
DECORATION = re.compile(r"^[\s>]*(?:[-*+]\s+|\d+[.)]\s+)?[\s>]*")

# Section fields inside a subject-declaring section. A label outside both declared sets is treated
# as a state carrier and fails closed; declaring a new narrative field is a deliberate change.
SECTION_STATE_LABELS = {
    "STATUS": "status",
    "STATE": "status",
    "DECISION": "decision",
    "AUTHORIZATION": "authorization",
    "AUTHORITY": "authority",
    "GOVERNING AUTHORITY": "authority",
    "CURRENT CANONICAL IMPLEMENTATION": "authority",
}
SECTION_NARRATIVE_LABELS = {"UX SUGGESTION UNDER CONSIDERATION"}

# Kind, decided from the carrier KEY only. An unrecognised qualifier is a status carrier, not an
# ignored one -- that polarity is what closes R6-B1.
KEY_KIND_WORDS = (
    ("decision", ("DECISION",)),
    ("authority", ("AUTHORITY", "GOVERNING", "IMPLEMENTATION", "CONTRACT")),
    ("authorization", ("AUTHORIZATION", "AUTHORIZED")),
)

# AT-D10.1: one canonical carrier expresses exactly ONE proposition. These are the structural
# constructions that make a value express more than one. The test is on SHAPE -- the rule is
# atomicity, not whether the extra clause happens to say something acceptable.
CLAUSE_CONSTRUCTS = (
    (re.compile(r";"), "a semicolon clause"),
    (re.compile(r"\n"), "a second value line"),
    (re.compile(r"[(\[{]|[)\]}]"), "a bracketed aside"),
    (re.compile(r"(?:^|\s)-{2,}(?:\s|$)"), "a dash comment clause"),
    (re.compile("[‒–—―]"), "an en/em dash clause"),
    (re.compile(r"\.(?:\s|$)"), "a sentence break"),
)

# Canonical carriers that must exist. Anti-vacuity by required COVERAGE, not by token counts:
# deleting or reshaping one of these (for example replacing the parenthesised heading marker with
# a dash-delimited title) removes a required carrier and fails.
# Granularity is (artifact, subject, kind, FORM). Without the form, reshaping the heading marker
# would leave the artifact's other status carriers satisfying the requirement, and the loss of a
# canonical carrier would go unnoticed by this check.
REQUIRED_CARRIERS = (
    (BINDING, "at-d09", "status", "register"),
    (BINDING, "at-d09", "status", "heading-status"),
    (BINDING, "at-d09", "status", "section-field"),
    (BINDING, "at-d09", "decision", "section-field"),
    (BINDING, "at-d09", "authority", "section-field"),
    (BINDING, "at-m2", "at-m2-authorization", "register"),
    (RESET, "at-d09", "status", "register"),
    (RESET, "at-m2", "at-m2-authorization", "register"),
    (MANIFEST, "at-d09", "status", "register"),
    (PRECEDENCE, "at-m2", "at-m2-authorization", "register"),
)


def undecorated(line: str) -> str:
    return DECORATION.sub("", line).replace("**", "").replace("`", "").strip()


def keyed_field(line: str) -> tuple[str, str] | None:
    """(key, inline value) split at the FIRST colon, or None when the line has no colon.

    DEF-R7-01: no character class, length bound or punctuation whitelist is applied to the key.
    The key is whatever precedes the first colon, so an unforeseen qualifier -- punctuated,
    decorated, or a 200-character noun phrase -- cannot make a carrier invisible. Whether that
    key belongs to a subject is decided separately, by SUBJECT_KEY_START, and never by what the
    key is called.
    """
    key, separator, value = undecorated(line).partition(":")
    if not separator:
        return None
    return key.strip(), value


def atomicity_verdict(value: str) -> str:
    """'' when the value is a single canonical proposition, else why it is not (AT-D10.1)."""
    if not value.strip():
        return "carrier value is empty"
    for pattern, construction in CLAUSE_CONSTRUCTS:
        if pattern.search(value):
            return f"non-atomic canonical value: contains {construction}"
    return ""


def carrier_verdict(kind: str, value: str) -> str:
    """AT-D10.1 atomicity, then AT-D10 allowed-state validation on the COMPLETE value.

    Nothing is discarded before validation. DEF-R7-02's escape was a trailing clause silently
    dropped as a "qualifier", which let an allowed head shield a second predicate; a carrier
    that carries more than one proposition is now rejected as non-atomic rather than truncated
    down to the acceptable part.
    """
    non_atomic = atomicity_verdict(value)
    if non_atomic:
        return non_atomic
    return state_verdict(kind, propositions(value))


def carrier_kind(subject: str, key: str, declared: str = "") -> str:
    if subject == "at-m2":
        return "at-m2-authorization"
    if declared:
        return declared
    upper = normalized_key(key)
    for kind, words in KEY_KIND_WORDS:
        if any(re.search(rf"\b{word}\b", upper) for word in words):
            return kind
    return "status"


def canonical_carriers(
    artifact: str, doc: str, subject: str
) -> list[tuple[str, int, str, str, str]]:
    """(artifact, line, form, kind, value) for every CANONICAL carrier of `subject`.

    Structural discovery only. Neither state vocabulary nor a key character whitelist decides
    what is a carrier.
    """
    if artifact in NON_CANONICAL_STATE_ARTIFACTS:
        return []
    ident = SUBJECT_PATTERNS[subject]
    starts_with_subject = SUBJECT_KEY_START[subject]
    found: list[tuple[str, int, str, str, str]] = []
    lines = doc.splitlines()
    fenced = False
    in_subject_section = False

    def carrier_value(index: int, inline: str) -> str:
        """The COMPLETE value: the inline text, or every continuation line (DEF-R7-02).

        Continuations are joined with a newline, which CLAUSE_CONSTRUCTS reads as a second
        proposition -- a value spread over two lines is two clauses, not a longer one.
        """
        if inline.strip():
            return inline.strip()
        parts: list[str] = []
        blanks = 0
        for following in lines[index + 1 :]:
            if not following.strip():
                if parts:
                    break
                blanks += 1
                if blanks > 2:
                    break
                continue
            if parts and not following.startswith((" ", "\t")):
                break
            parts.append(following.strip())
        return "\n".join(parts)

    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue

        if line.startswith("#"):
            in_subject_section = bool(ident.search(line))
            # Only the parenthesised marker is a declared heading carrier. A heading without one
            # states no canonical status; it is a title. Removing the marker from a required
            # heading carrier is caught by REQUIRED_CARRIERS, not by guessing at prose. Two
            # markers are two propositions and fail AT-D10.1.
            markers = [m.strip() for m in re.findall(r"\(([^)]*)\)", line) if m.strip()]
            if in_subject_section and markers:
                found.append(
                    (
                        artifact,
                        index + 1,
                        "heading-status",
                        carrier_kind(subject, ""),
                        "\n".join(markers),
                    )
                )
            continue

        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and ident.search(cells[0]):
                found.append(
                    (
                        artifact,
                        index + 1,
                        "table-state",
                        carrier_kind(subject, cells[0]),
                        "\n".join(c for c in cells[1:] if c),
                    )
                )
            continue

        field = keyed_field(line)
        if not field:
            continue
        key, inline = field

        if starts_with_subject.match(key):
            found.append(
                (
                    artifact,
                    index + 1,
                    "register" if fenced else "field",
                    carrier_kind(subject, key),
                    carrier_value(index, inline),
                )
            )
            continue

        # A label carrying no subject of its own inherits the section's subject. It binds only
        # inside a fenced block: with the subject absent from the key, the fence is the structure
        # that separates a canonical field from a sentence that happens to contain a colon.
        if fenced and in_subject_section and subject == "at-d09":
            label = normalized_key(key)
            if label in SECTION_NARRATIVE_LABELS:
                continue
            found.append(
                (
                    artifact,
                    index + 1,
                    "section-field",
                    carrier_kind(subject, label, SECTION_STATE_LABELS.get(label, "")),
                    carrier_value(index, inline),
                )
            )
    return found


def domain_carriers(subject: str) -> list[tuple[str, int, str, str, str]]:
    found: list[tuple[str, int, str, str, str]] = []
    for artifact in sorted(p for p in AT_M1_EXPECTED_PATHS if p.endswith(".md")):
        found.extend(canonical_carriers(artifact, read(artifact), subject))
    return found


def unauthorized_carriers(subject: str) -> list[str]:
    """Every canonical carrier whose CURRENT value is not an allowed state for its kind."""
    failures = []
    for artifact, line, form, kind, value in domain_carriers(subject):
        verdict = carrier_verdict(kind, value)
        if verdict:
            failures.append(f"{artifact}:{line} [{form}/{kind}] {value!r} -- {verdict}")
    return failures


def missing_required_carriers() -> list[str]:
    missing = []
    for artifact, subject, kind, form in REQUIRED_CARRIERS:
        present = any(
            found_kind == kind and found_form == form
            for found_artifact, _, found_form, found_kind, _ in domain_carriers(subject)
            if found_artifact == artifact
        )
        if not present:
            missing.append(f"{artifact} [{subject}/{kind}/{form}]")
    return missing


def contradicting_carriers(subject: str) -> list[str]:
    """Two canonical carriers of the same kind asserting opposite polarity on the same term."""
    polarity: dict[tuple[str, str], set[bool]] = {}
    origin: dict[tuple[str, str], list[str]] = {}
    for artifact, line, _, kind, value in domain_carriers(subject):
        for affirmed, term in propositions(value):
            polarity.setdefault((kind, term), set()).add(affirmed)
            origin.setdefault((kind, term), []).append(f"{artifact}:{line}")
    return [
        f"{kind}/{term} asserted both ways by {origin[(kind, term)]}"
        for (kind, term), seen in sorted(polarity.items())
        if len(seen) > 1
    ]


def prose_contradiction_advisories(subject: str) -> list[str]:
    """AT-D10 section 9: deterministic, NON-BLOCKING, never a correctness prerequisite.

    Reports register-shaped lines in NON-canonical records whose value contradicts canonical
    state. Incomplete coverage is acceptable by contract; this never changes canonical truth.
    """
    notes = []
    starts_with_subject = SUBJECT_KEY_START[subject]
    for artifact in NON_CANONICAL_STATE_ARTIFACTS:
        for index, line in enumerate(read(artifact).splitlines()):
            field = keyed_field(line)
            if not field or not starts_with_subject.match(field[0]) or not field[1].strip():
                continue
            # Deliberately the lenient reading: a record narrates, so its trailing clauses are
            # commentary. Atomicity is a rule about CANONICAL carriers, not about records.
            verdict = state_verdict(
                carrier_kind(subject, field[0]), propositions(current_value(field[1]))
            )
            if verdict:
                notes.append(f"{artifact}:{index + 1} {field[1].strip()[:60]!r} -- {verdict}")
    return notes


def claims_at_d09_closed(text: str) -> bool:
    """True if the text, read as a current proposition, closes AT-D09."""
    props = propositions(current_value(text))
    closure = set(AT_D09_CLOSURE_TERMS)
    openish = set(AT_D09_OPEN_TERMS)
    if any(affirm and term in closure for affirm, term in props):
        return True
    return any(not affirm and term in openish for affirm, term in props)


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
    expect(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", AT_M1_STAGE_HEAD, "HEAD"], cwd=ROOT, check=False
        ).returncode
        == 0,
        "check01a",
        f"the reviewed AT-M1 stage head {AT_M1_STAGE_HEAD_SHORT} is not reachable from HEAD; the "
        "reviewed implementation must never leave the canonical history",
    )
    expect(
        git("rev-parse", f"{AT_M1_MERGE_COMMIT}^2") == AT_M1_STAGE_HEAD,
        "check01c",
        f"the canonical merge {AT_M1_MERGE_COMMIT_SHORT} does not have the reviewed stage head "
        f"{AT_M1_STAGE_HEAD_SHORT} as its merged parent; the frozen pointer has been moved",
    )
    expect(
        git("rev-parse", f"{AT_M1_MERGE_COMMIT}^1") == AT_M1_BASELINE,
        "check01d",
        f"the canonical merge {AT_M1_MERGE_COMMIT_SHORT} does not sit directly on the canonical "
        f"baseline {AT_M1_BASELINE_SHORT}; the merge topology has been rewritten",
    )
    # FROZEN: what AT-M1 was reviewed and accepted to be. Independent of later commits.
    stage_changed = changed_paths(AT_M1_POSITIVE_RANGE)
    # LIVE: what exists now. Rejection logic below reads this one, never the frozen set.
    head_changed = changed_paths(AT_M1_CURRENT_RANGE)
    expect(
        stage_changed == AT_M1_EXPECTED_PATHS,
        "check02",
        "reviewed stage paths are not exactly the AT-M1 registry: "
        f"unexpected={sorted(stage_changed - AT_M1_EXPECTED_PATHS)} "
        f"missing={sorted(AT_M1_EXPECTED_PATHS - stage_changed)}",
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
        p for p in stage_changed if "gov1" in p or p.startswith("scripts/verify_step66")
    )
    expect(
        gov1_contamination == [],
        "check03c",
        f"GOV1 paths contaminate the AT-M1 positive scope (A-01 regression): {gov1_contamination}",
    )

    # --- 2. no implementation (INV-10) --------------------------------------------------------
    # HEAD-relative on purpose: freezing these at the stage head would blind them to anything
    # added after the reviewed implementation.
    offenders = forbidden_scope_offenders(head_changed)
    expect(offenders == [], "check04", f"AT-M1 introduced implementation paths: {offenders}")
    breached = protected_breaches(head_changed)
    expect(breached == [], "check05", f"a protected file was modified: {breached}")
    expect(
        "source/progress.md" not in head_changed,
        "check06",
        "source/progress.md must remain unchanged (ADV-DRIFT-PROGRESS-01)",
    )
    expect(
        not any(p.endswith(".sql") for p in head_changed),
        "check07",
        "AT-M1 must create no migration",
    )
    expect(
        not any(p.endswith((".tsx", ".ts", ".jsx", ".css")) for p in head_changed),
        "check08",
        "AT-M1 must create no frontend source",
    )
    expect(
        sorted(p for p in stage_changed if not p.startswith("docs/")) == sorted([VERIFIER, TESTS]),
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
    # AT-M1-RM2 (DEF-R2-02). These were whole-document substring tests: the binding contract holds
    # several unrelated OPEN and DEFERRED tokens, so any single AUTHORITATIVE AT-D09 surface could
    # be flipped to RESOLVED/CLOSED while both checks stayed green. Each authoritative surface is
    # now targeted structurally and tested for closure claims on that surface alone.
    # AT-M1-RM3 (DEF-R3-01). RM2 enumerated the surfaces a reviewer named. Two more state AT-D09's
    # status: the section-8 authorization register and the section-6 heading marker. A closure
    # claim on either passed every check and every test, so both are now read structurally, and
    # check92j rejects any future AT-D09 status surface that no named check reads.
    d09_section = section_text(binding, "## 6. AT-D09")
    d09_summary = labelled_line(binding, "AT-D09:")
    d09_status = labelled_line(d09_section, "STATUS:")
    d09_decision = indented_value(d09_section, "Decision:")
    d09_register = labelled_line(section_text(binding, "## 8. Authorization status"), "AT_D09:")
    d09_heading = line_with(binding, "## 6. AT-D09")

    expect(
        d09_section != "",
        "check92",
        "the AT-D09 section (## 6.) is missing from the binding decisions contract",
    )
    expect(
        d09_summary != "" and "OPEN" in d09_summary.upper(),
        "check92a",
        f"the AT-D09 summary statement does not record it as OPEN: {d09_summary!r}",
    )
    expect(
        not claims_at_d09_closed(d09_summary),
        "check92b",
        f"the AT-D09 summary statement claims the question is answered: {d09_summary!r}",
    )
    expect(
        d09_status != "" and "OPEN" in d09_status.upper() and "DEFERRED" in d09_status.upper(),
        "check92c",
        f"the AT-D09 section-6 STATUS line is not OPEN / DEFERRED: {d09_status!r}",
    )
    expect(
        not claims_at_d09_closed(d09_status),
        "check92d",
        f"the AT-D09 section-6 STATUS line claims closure: {d09_status!r}",
    )
    expect(
        d09_decision.upper() == "DEFERRED",
        "check92e",
        f"the AT-D09 section-6 Decision value is not DEFERRED: {d09_decision!r}",
    )
    expect(
        d09_register != "" and "OPEN" in d09_register.upper(),
        "check92f",
        f"the section-8 authorization register does not record AT-D09 as OPEN: {d09_register!r}",
    )
    expect(
        not claims_at_d09_closed(d09_register),
        "check92g",
        f"the section-8 authorization register claims AT-D09 is answered: {d09_register!r}",
    )
    expect(
        d09_heading != "" and "(OPEN)" in d09_heading.upper(),
        "check92h",
        f"the AT-D09 section-6 heading does not mark the question OPEN: {d09_heading!r}",
    )
    expect(
        not claims_at_d09_closed(d09_heading),
        "check92i",
        f"the AT-D09 section-6 heading claims the question is answered: {d09_heading!r}",
    )
    # AT-M1-RM6 (AT-D10). Structured carriers are the sole canonical authority. Discovery is
    # structural and precedes interpretation: a subject-keyed field in a canonical artifact is a
    # carrier whatever its qualifier and whatever its value, and an uninterpretable value fails
    # closed. Free prose is no longer a state channel at all.
    d09_unauthorized = unauthorized_carriers("at-d09")
    expect(
        d09_unauthorized == [],
        "check92j",
        f"a canonical AT-D09 carrier is not in an allowed state: {d09_unauthorized!r}",
    )
    d09_kinds = {kind for _, _, _, kind, _ in domain_carriers("at-d09")}
    expect(
        d09_kinds <= {"status", "decision", "authorization", "authority"},
        "check92k",
        f"an AT-D09 carrier was assigned an unknown kind: {sorted(d09_kinds)!r}",
    )
    missing_carriers = missing_required_carriers()
    expect(
        missing_carriers == [],
        "check92l",
        f"a required canonical state carrier is no longer discoverable: {missing_carriers!r}",
    )
    m2_unauthorized = unauthorized_carriers("at-m2")
    expect(
        m2_unauthorized == [],
        "check92m",
        f"a canonical AT-M2 carrier no longer states NOT AUTHORIZED: {m2_unauthorized!r}",
    )
    conflicts = contradicting_carriers("at-d09") + contradicting_carriers("at-m2")
    expect(
        conflicts == [],
        "check92n",
        f"canonical carriers assert contradictory governance state: {conflicts!r}",
    )
    expect(
        "must not canonicalize permissive continuation" in flat(d09_section),
        "check93",
        "the AT-D09 section no longer declares that AT-M1 must not canonicalize permissive "
        "continuation",
    )
    expect(
        # AT-D10.1 removed the parenthetical aside from the carrier value; the assertion is the
        # same, written atomically.
        "Step 66C.4 clarification expiry contract REMAINS AUTHORITATIVE" in flat(d09_section),
        "check93a",
        "the AT-D09 section no longer preserves the Step 66C.4 clarification expiry contract as "
        "authoritative",
    )
    expect(
        "SUPERSEDED" not in d09_section.upper() and "SUPERSEDES" not in d09_section.upper(),
        "check93b",
        "the AT-D09 section claims the Step 66C.4 clarification contract is superseded",
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
        not any("delivery_acceptance" in p or p.startswith("migrations/036") for p in head_changed),
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
    # Target the AT-D09 STATEMENT, not the whole document: an unrelated line already contains
    # "OPEN" (OPEN_PRODUCT_OWNER_DECISIONS), so a document-wide search cannot detect a closure.
    at_d09 = line_with(precedence, "AT-D09")
    expect(
        at_d09 != "",
        "check104g",
        "the precedence record does not mention AT-D09 at all",
    )
    expect(
        "OPEN" in at_d09.upper() and "DEFERRED" in at_d09.upper(),
        "check104g1",
        f"the AT-D09 statement does not keep it OPEN / DEFERRED: {at_d09!r}",
    )
    closure_claims = sorted(
        claim for claim in ("RESOLVED", "CLOSED", "BINDING", "ACCEPTED") if claim in at_d09.upper()
    )
    expect(
        closure_claims == [],
        "check104g2",
        f"the AT-D09 statement claims closure {closure_claims}: {at_d09!r}",
    )
    expect(
        "NOT decided" in at_d09 or "not decided" in at_d09,
        "check104g3",
        f"the AT-D09 statement does not record that AT-M1 leaves it undecided: {at_d09!r}",
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
    # Inverted at AT-M1-M1: before the merge this asserted PENDING CANONICAL MERGE. The claim is
    # now the opposite one, and it is pinned to the recorded merge so it cannot be made true by
    # wording alone.
    at_m1_entry = flat_manifest.split("AT-M1 Autonomous team", 1)[-1][:400].upper()
    expect(
        "CLOSED / CANONICAL" in at_m1_entry
        and "PR #29 MERGED" in at_m1_entry
        and AT_M1_MERGE_COMMIT_SHORT.upper() in at_m1_entry
        and AT_M1_STAGE_HEAD_SHORT.upper() in at_m1_entry,
        "check104o",
        "the milestone manifest does not register AT-M1 as CLOSED / CANONICAL with the merged "
        f"PR #29, reviewed stage head {AT_M1_STAGE_HEAD_SHORT} and merge {AT_M1_MERGE_COMMIT_SHORT}",
    )
    expect(
        "PENDING CANONICAL MERGE" not in flat_manifest.upper(),
        "check104o1",
        "the milestone manifest still says AT-M1 is pending canonical merge after PR #29 merged",
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

    # AT-M1-RM2 (DEF-R2-01). The canonical registry carried two measurably false evidence
    # strings -- "principal_id: 0 occurrences" and "Only 2 matches for handoff" -- while the
    # capability STATES were correct. AT-M2 is scoped by this registry, so a reader would have
    # treated both names as free. These checks read the structured entries, not the whole file.
    by_name = {c.get("capability"): c for c in caps}
    principal_entry = by_name.get("AgentPrincipal", {})
    handoff_entry = by_name.get("Handoff", {})
    principal_evidence = str(principal_entry.get("evidence", ""))
    handoff_evidence = str(handoff_entry.get("evidence", ""))

    expect(
        principal_entry.get("state") == "CONTRACT_ONLY",
        "check128a",
        f"AgentPrincipal is no longer CONTRACT_ONLY: {principal_entry.get('state')!r}",
    )
    expect(
        "principal_id: 0 occurrences" not in principal_evidence
        and "principal_id: 0" not in principal_evidence,
        "check128b",
        "the AgentPrincipal evidence still asserts principal_id has 0 occurrences, which is "
        "measurably false and would tell AT-M2 the name is free",
    )
    expect(
        "ActorPrincipal: 0" in principal_evidence,
        "check128c",
        "the AgentPrincipal evidence no longer records that ActorPrincipal itself is absent",
    )
    expect(
        "authorization" in principal_evidence.lower()
        and "Actor.principal_id" in principal_evidence,
        "check128d",
        "the AgentPrincipal evidence does not distinguish the existing task/authorization "
        "Actor.principal_id from the absent ActorPrincipal abstraction",
    )
    expect(
        handoff_entry.get("state") == "NOT_IMPLEMENTED",
        "check128e",
        f"Handoff is no longer NOT_IMPLEMENTED: {handoff_entry.get('state')!r}",
    )
    expect(
        "Only 2 matches" not in handoff_evidence,
        "check128f",
        "the Handoff evidence still asserts only 2 handoff matches, which is measurably false "
        "and would tell AT-M2 the name is free",
    )
    expect(
        "HandoffSummary" in handoff_evidence and "delivery_package" in handoff_evidence,
        "check128g",
        "the Handoff evidence does not identify the legacy delivery-package symbols that "
        "already occupy the name",
    )
    expect(
        "work-transfer" in handoff_evidence and "absent" in handoff_evidence.lower(),
        "check128h",
        "the Handoff evidence does not distinguish legacy delivery handoff from the absent "
        "autonomous agent work-transfer primitive",
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
