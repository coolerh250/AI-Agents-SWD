#!/usr/bin/env python3
"""Step 66D-BE1-CR1 -- canonical contract verifier for the DeliveryReviewTask active-state amendment.

Deterministic and read-only. Confirms that 66D-D05 is recorded as binding, that active state is the
structural predicate closed_at IS NULL, that no DeliveryReviewTask lifecycle enum was invented, that
DeliverySubmission.status is never mirrored as task lifecycle authority, that the ARCH1 mirroring
sentence is explicitly superseded while the DESIGN non-interchangeability requirement is preserved,
and that this stage created no implementation, migration or runtime change.

Positive scope is a fixed baseline plus an explicit path registry compared by set equality.

Starts no runtime, container, database or external provider.

Marker: STEP66D_BE1_CR1_ACTIVE_STATE_CONTRACT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "STEP66D_BE1_CR1_ACTIVE_STATE_CONTRACT_VERIFY"

CR1_BASELINE = "af40b3bf9792fe8182e9620fb9d134af67cf4a12"
CR1_BASELINE_SHORT = "af40b3b"

# Step 66D-BE1-CR1-M1 post-merge scope freeze.
#
# While PR #27 was open the positive scope was CR1_BASELINE...HEAD, safe because HEAD was the PR
# head and was bounded by CR1_EXPECTED_PATHS. Merged, HEAD is main and advances with every later
# authorized stage, so it must never again be the positive endpoint: this stage's scope is the
# immutable range below.
CR1_STAGE_HEAD = "4fe5204e74774d2087c69bea7358f4739122880e"
CR1_POSITIVE_RANGE = f"{CR1_BASELINE}...{CR1_STAGE_HEAD}"

# The positive scope above is frozen. The current-state rejection guard must NOT be frozen with it:
# an implementation or runtime path added by any later commit still has to be caught. This anchor is
# deliberately HEAD-relative, feeds the denylist only, and can never widen the positive scope.
CR1_RUNTIME_GUARD_ANCHOR = CR1_BASELINE

CONTRACTS = "docs/contracts/66d-delivery-acceptance"
ARCH = "docs/architecture/66d-delivery-acceptance"
DESIGN = "docs/design/66d-delivery-acceptance"
HANDOFF = "docs/handoffs/66d-delivery-acceptance"

D05 = f"{CONTRACTS}/step66d-d05-review-task-active-state-amendment.md"
BINDING = f"{CONTRACTS}/step66d-delivery-decision-model-binding-decisions.md"
REGISTRY = f"{CONTRACTS}/step66d-canonical-terminology-registry.md"
DOMAIN = f"{ARCH}/step66d-arch1-domain-and-state-model.md"
INBOX = f"{DESIGN}/step66d-design-delivery-inbox-spec.md"
MANIFEST = f"{DESIGN}/step66d-design-contract-manifest.json"
MATRIX = f"{HANDOFF}/step66d-canonical-conflict-supersession-matrix.md"
EVIDENCE = f"{HANDOFF}/step66d-be1-cr1-active-state-contract-evidence.md"
VERIFIER = "scripts/verify_step66d_be1_cr1_active_state_contract.py"
TESTS = "tests/test_step66d_be1_cr1_active_state_contract.py"

# Step 66D-BE1-CR1-RM1: exactly one historical test path is authorized, by literal, to repair the
# DESIGN-M1 drifting-HEAD diff range. This is a single named file, never a prefix, wildcard or
# historical-test category, so any OTHER historical verifier or test is still rejected.
AUTHORIZED_HISTORICAL_PATHS = frozenset({"tests/test_step66d_design_m1_canonical_merge.py"})

CR1_EXPECTED_PATHS = (
    frozenset({D05, BINDING, REGISTRY, DOMAIN, INBOX, MANIFEST, MATRIX, EVIDENCE, VERIFIER, TESTS})
    | AUTHORIZED_HISTORICAL_PATHS
)

# Values that must never be introduced as a DeliveryReviewTask lifecycle enum.
FORBIDDEN_LIFECYCLE_VALUES = ("OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED", "PENDING", "ACTIVE")

FORBIDDEN_SCOPE_PREFIXES = (
    "apps/",
    "agents/",
    "services/",
    "shared/",
    "migrations/",
    "infra/",
    "helm/",
    "k8s/",
    ".github/workflows/",
    "runtime/",
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


def manifest() -> dict:
    try:
        return json.loads(read(MANIFEST))
    except json.JSONDecodeError:
        return {}


def review_task_spans(text: str) -> list[tuple[int, int]]:
    """Offset spans of the document that talk about the review task.

    Spans are returned as offsets into the ORIGINAL text so that every context window is computed
    from real neighbouring prose. Concatenating the chunks first would let one span's negation
    wording vouch for a different span, which is precisely how a tampered claim could hide.
    """
    spans = []
    for match in re.finditer(r"(?im)^.*DeliveryReviewTask.*$", text):
        spans.append((match.start(), min(len(text), match.start() + 900)))
    return spans


def in_span(index: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in spans)


def denegate(text: str) -> str:
    """Strip SQL null predicates before negation sniffing.

    "closed_at IS NOT NULL" must not read as a negation of the surrounding claim.
    """
    return re.sub(r"(?i)\bIS\s+(NOT\s+)?NULL\b", " ", text)


def main() -> int:
    d05 = read(D05)
    binding = read(BINDING)
    registry = read(REGISTRY)
    domain = read(DOMAIN)
    inbox = read(INBOX)
    matrix = read(MATRIX)
    evidence = read(EVIDENCE)
    data = manifest()
    block = data.get("review_task_active_state", {})

    # --- 1. baseline and exact positive scope -------------------------------------------------
    expect(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", CR1_BASELINE, "HEAD"], cwd=ROOT, check=False
        ).returncode
        == 0,
        "check01",
        "the CR1 canonical baseline af40b3b is not an ancestor of HEAD",
    )
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", CR1_POSITIVE_RANGE).splitlines()
        if line.strip()
    }
    current_state = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{CR1_RUNTIME_GUARD_ANCHOR}...HEAD").splitlines()
        if line.strip()
    }
    expect(
        changed == CR1_EXPECTED_PATHS,
        "check02",
        f"changed-path set != CR1_EXPECTED_PATHS; missing={sorted(CR1_EXPECTED_PATHS - changed)} "
        f"unexpected={sorted(changed - CR1_EXPECTED_PATHS)}",
    )
    expect(
        len(CR1_EXPECTED_PATHS) == 11,
        "check03",
        f"the CR1 path registry is {len(CR1_EXPECTED_PATHS)} paths, expected exactly 11",
    )
    expect(
        AUTHORIZED_HISTORICAL_PATHS == {"tests/test_step66d_design_m1_canonical_merge.py"},
        "check03b",
        f"exactly one literal historical path may be authorized, got "
        f"{sorted(AUTHORIZED_HISTORICAL_PATHS)}",
    )
    unauthorized_historical = sorted(
        p
        for p in changed
        if re.search(r"(verify|test)_step66", p)
        and "be1_cr1_active_state_contract" not in p
        and p not in AUTHORIZED_HISTORICAL_PATHS
    )
    expect(
        not unauthorized_historical,
        "check03c",
        f"unauthorized historical verifier/test paths changed: {unauthorized_historical}",
    )
    m1_test = read("tests/test_step66d_design_m1_canonical_merge.py")
    expect(
        'f"{MERGE_COMMIT}..HEAD"' not in m1_test,
        "check03d",
        "the DESIGN-M1 historical test still uses a drifting MERGE_COMMIT..HEAD range",
    )
    expect(
        'RECORD_COMMIT = "af40b3bf9792fe8182e9620fb9d134af67cf4a12"' in m1_test
        and 'f"{MERGE_COMMIT}..{RECORD_COMMIT}"' in m1_test,
        "check03e",
        "the DESIGN-M1 historical test does not pin the frozen e4efb88..af40b3b record range",
    )
    # Rejection-only, evaluated against CURRENT state rather than the frozen positive range, so an
    # implementation path introduced by any later commit is still caught. This never admits a path
    # into the positive scope asserted above.
    scanned = current_state or changed
    offenders = sorted(p for p in scanned if p.startswith(FORBIDDEN_SCOPE_PREFIXES))
    expect(not offenders, "check04", f"implementation/runtime paths changed: {offenders}")
    expect(
        "source/progress.md" not in changed,
        "check04b",
        "source/progress.md must not be modified by this stage",
    )

    # --- 2. 66D-D05 exists and is binding ------------------------------------------------------
    expect(bool(d05), "check05", "the 66D-D05 amendment document is missing")
    expect("66D-D05" in d05 and "BINDING" in d05, "check06", "66D-D05 is not recorded as binding")
    expect("Product Owner" in d05, "check06b", "66D-D05 does not record the decision authority")
    expect(
        CR1_BASELINE in d05 or CR1_BASELINE_SHORT in d05,
        "check07",
        "66D-D05 does not record the canonical baseline",
    )
    expect("66D-D05" in binding, "check08", "the binding decisions registry does not carry 66D-D05")
    for requirement in (f"D05-R{n}" for n in range(1, 11)):
        expect(
            requirement in binding,
            "check09",
            f"binding decisions registry is missing {requirement}",
        )

    # --- 3. the predicates ---------------------------------------------------------------------
    for label, text in (
        ("D05", d05),
        ("binding", binding),
        ("domain", domain),
        ("registry", registry),
    ):
        expect(
            "closed_at IS NULL" in text,
            "check10",
            f"{label} does not state the active predicate closed_at IS NULL",
        )
        expect(
            "closed_at IS NOT NULL" in text,
            "check11",
            f"{label} does not state the closed predicate closed_at IS NOT NULL",
        )
    expect(
        block.get("review_task_active_predicate") == "closed_at_is_null",
        "check12",
        f"manifest active predicate is {block.get('review_task_active_predicate')!r}",
    )
    expect(
        block.get("review_task_closed_predicate") == "closed_at_is_not_null",
        "check13",
        f"manifest closed predicate is {block.get('review_task_closed_predicate')!r}",
    )
    expect(block.get("decision_id") == "66D-D05", "check14", "manifest block is not tagged 66D-D05")

    # --- 4. submission-status mirroring is forbidden -------------------------------------------
    expect(
        block.get("submission_status_mirroring") == "forbidden",
        "check15",
        "the manifest does not forbid submission-status mirroring",
    )
    for label, text in (("D05", d05), ("binding", binding)):
        expect(
            re.search(
                r"(?i)(must not|shall not|never)\s+mirror\s+DeliverySubmission\.status", flat(text)
            )
            is not None,
            "check16",
            f"{label} does not forbid mirroring DeliverySubmission.status into the review task",
        )
    # No document may re-assert the mirroring statement as current authority. A quotation of the
    # superseded sentence is allowed only inside superseded / conflict framing.
    for label, text in (("D05", d05), ("binding", binding), ("inbox", inbox), ("matrix", matrix)):
        for match in re.finditer(r"(?i)mirrors submission review state", text):
            window = flat(text[max(0, match.start() - 900) : match.end() + 900]).upper()
            expect(
                any(
                    cue in window
                    for cue in ("SUPERSEDED", "SUPERSEDES", "WITHDRAWN", "NOT AUTHORITATIVE")
                ),
                "check17",
                f"{label} repeats the mirroring statement without superseded framing",
            )

    # --- 5. no review-task lifecycle enum ------------------------------------------------------
    expect(
        block.get("review_task_lifecycle_enum") == "deferred",
        "check18",
        "the manifest does not defer the review-task lifecycle enum",
    )
    for label, text in (("D05", d05), ("binding", binding), ("registry", registry)):
        expect(
            re.search(r"(?i)lifecycle enum[^.\n]{0,40}(not defined|deferred)", flat(text))
            is not None,
            "check19",
            f"{label} does not record the review-task lifecycle enum as not defined / deferred",
        )
    # A forbidden value may only appear near DeliveryReviewTask when it is explicitly negated or
    # attributed to AcceptanceFollowUpItem.
    for label, text in (
        ("D05", d05),
        ("binding", binding),
        ("registry", registry),
        ("domain", domain),
    ):
        spans = review_task_spans(text)
        for value in FORBIDDEN_LIFECYCLE_VALUES:
            for match in re.finditer(rf"\b{value}\b", text):
                if not in_span(match.start(), spans):
                    continue
                # "ACTIVE-STATE" / "ACTIVE_STATE" is prose about the structural predicate, not an
                # enum value declaration.
                if text[match.end() : match.end() + 6].upper().startswith(("-STATE", "_STATE")):
                    continue
                # Window is computed from the ORIGINAL text, never from a concatenation.
                window = flat(text[max(0, match.start() - 320) : match.end() + 320]).upper()
                negated = any(
                    cue in window
                    for cue in (
                        "MUST NOT",
                        "NOT DEFINED",
                        "FORBIDDEN",
                        "DEFERRED",
                        "ACCEPTANCEFOLLOWUPITEM",
                        "NEVER",
                        "NOT BE INTRODUCED",
                        "NOT BE REUSED",
                        "IS NOT THE VALUE",
                    )
                )
                expect(
                    negated,
                    "check20",
                    f"{label} may declare {value} as a DeliveryReviewTask lifecycle value",
                )

    # --- 6. delivery_review_task_status stays deferred ------------------------------------------
    expect(
        block.get("delivery_review_task_status") == "planned_not_implemented",
        "check21",
        "the manifest does not defer delivery_review_task_status",
    )
    filters = {f.get("name"): f for f in data.get("inbox_filters", [])}
    task_filter = filters.get("delivery_review_task_status", {})
    expect(
        {"delivery_review_task_status", "delivery_submission_status"} <= set(filters),
        "check22",
        "the two distinct inbox status filters are no longer both present",
    )
    expect(
        "NOT DEFINED" in str(task_filter.get("enum_source", "")).upper(),
        "check23",
        "the review-task filter no longer records its enum as undefined",
    )
    expect(
        "DeliverySubmission.status" not in str(task_filter.get("source_field", "")),
        "check24",
        "the review-task filter is sourced from DeliverySubmission.status",
    )
    expect(
        re.search(r"(?i)must not map\s+DeliverySubmission\.status", flat(inbox)) is not None,
        "check25",
        "the inbox spec does not forbid mapping DeliverySubmission.status onto the filter",
    )
    expect(
        re.search(r"(?i)(planned|deferred)", flat(str(task_filter))) is not None,
        "check25b",
        "the review-task filter is not marked planned/deferred",
    )

    # --- 7. persistence invariant ---------------------------------------------------------------
    expect(
        block.get("persistence_invariant") == "at_most_one_active_per_delivery_submission_id",
        "check26",
        f"manifest persistence invariant is {block.get('persistence_invariant')!r}",
    )
    expect(
        block.get("partial_unique_boundary") == "delivery_submission_id",
        "check27",
        "the partial uniqueness boundary is not delivery_submission_id",
    )
    for label, text in (("D05", d05), ("binding", binding)):
        expect(
            re.search(r"(?i)at most one", flat(text)) is not None,
            "check28",
            f"{label} does not state the AT MOST ONE invariant",
        )
        expect(
            re.search(r"(?i)exactly one .{0,40}always exists", flat(text)) is None,
            "check29",
            f"{label} claims the database guarantees a task always exists",
        )
    expect(
        block.get("required_existence_semantics") == "deferred",
        "check30",
        "required-existence semantics are not deferred in the manifest",
    )

    # --- 8. closed_at carries no outcome meaning ------------------------------------------------
    expect(
        block.get("closed_at_implies_decision") is False,
        "check31",
        "the manifest does not record that closed_at implies no decision",
    )
    for label, text in (("D05", d05), ("binding", binding), ("registry", registry)):
        expect(
            re.search(
                r"(?i)closed_at (never|is not|does not)|never implies|closed_at\s*==\s*acceptance",
                flat(text),
            )
            is not None,
            "check32",
            f"{label} does not state that closed_at carries no outcome meaning",
        )

    # --- 9. transitions deferred ----------------------------------------------------------------
    expect(
        block.get("transition_semantics") == "deferred",
        "check33",
        "transition semantics are not deferred in the manifest",
    )
    for term in ("reopen", "automatic closure"):
        expect(
            re.search(rf"(?i){term}", flat(d05)) is not None,
            "check34",
            f"66D-D05 does not name {term} among the deferred transitions",
        )
    expect(
        re.search(r"(?i)(reopen|transition)[^.\n]{0,80}defer", flat(d05)) is not None,
        "check35",
        "66D-D05 does not defer reopen/transition semantics",
    )

    # --- 10. ARCH1 superseded, DESIGN preserved -------------------------------------------------
    expect(
        "SUPERSEDED BY 66D-D05" in domain,
        "check36",
        "the ARCH1 domain model does not mark the mirroring statement superseded",
    )
    expect(
        "mirrors submission review state" in domain,
        "check37",
        "the original ARCH1 sentence was deleted instead of annotated",
    )
    expect(
        "NOT AUTHORITATIVE FOR BE1 PERSISTENCE" in domain,
        "check38",
        "the ARCH1 supersession does not state it is not authoritative for BE1 persistence",
    )
    expect(
        "not interchangeable" in flat(inbox).lower(),
        "check39",
        "the DESIGN non-interchangeability requirement was removed",
    )
    expect(
        block.get("preserves", "").lower().find("not interchangeable") >= 0,
        "check40",
        "the manifest does not record the preserved DESIGN distinction",
    )
    expect(
        "66D-D05" in matrix and "closed_at" in matrix,
        "check41",
        "the conflict supersession matrix does not record the 66D-D05 resolution",
    )
    expect(
        re.search(r"(?i)DESIGN did not define review.task lifecycle values", flat(matrix))
        is not None,
        "check42",
        "the matrix does not state that DESIGN never defined lifecycle values",
    )

    # --- 10b. active state must never be defined from a status enum ------------------------------
    for label, text in (
        ("D05", d05),
        ("binding", binding),
        ("registry", registry),
        ("domain", domain),
    ):
        for match in re.finditer(
            r"(?i)\bactive\b[^.\n]{0,40}?(?::=|\biff\b|\bis\b|\bmeans\b)[^.\n]{0,80}?\bstatus\b",
            text,
        ):
            window = flat(text[max(0, match.start() - 260) : match.end() + 260]).upper()
            expect(
                any(cue in window for cue in ("MUST NOT", "FORBIDDEN", "NEVER", "NOT DEFINED")),
                "check48",
                f"{label} defines active state from a status enum: {flat(match.group(0))!r}",
            )

    # --- 10c. closed_at must never be asserted to imply a decision -------------------------------
    for label, text in (
        ("D05", d05),
        ("binding", binding),
        ("registry", registry),
        ("domain", domain),
        ("matrix", matrix),
    ):
        for match in re.finditer(
            r"(?i)closed_at[^.\n]{0,60}?\b(implies|means|indicates|signals)\b[^.\n]{0,80}",
            text,
        ):
            phrase = denegate(flat(match.group(0))).upper()
            window = denegate(flat(text[max(0, match.start() - 200) : match.end() + 200])).upper()
            mentions_outcome = any(
                token in phrase
                for token in ("DECISION", "ACCEPT", "REJECT", "EXPIRED", "ARCHIVED", "QA")
            )
            negated = any(
                cue in phrase for cue in ("NEVER", "NOT ", "MUST NOT", "FORBIDDEN", "IMPLIES NO")
            )
            expect(
                (not mentions_outcome) or negated,
                "check49",
                f"{label} asserts closed_at implies an outcome: {flat(match.group(0))!r}",
            )

    # --- 10d. reopen / closure transitions must not be defined here ------------------------------
    for label, text in (
        ("D05", d05),
        ("binding", binding),
        ("registry", registry),
        ("domain", domain),
    ):
        for match in re.finditer(
            r"(?i)\breopen\w*\b[^.\n]{0,100}",
            text,
        ):
            phrase = flat(match.group(0)).upper()
            window = flat(text[max(0, match.start() - 240) : match.end() + 240]).upper()
            defines = any(
                cue in phrase
                for cue in (
                    " SETS ",
                    " CLEARS ",
                    " MUST ",
                    " SHALL ",
                    " ALLOWED",
                    " PERMITTED",
                    " WHEN ",
                )
            )
            deferred = any(
                cue in phrase or cue in window
                for cue in ("DEFER", "NOT DEFINE", "MUST NOT", "UNIMPLEMENTED", "NOT IMPLEMENT")
            )
            expect(
                (not defines) or deferred,
                "check50",
                f"{label} defines reopen semantics: {flat(match.group(0))!r}",
            )

    # --- 11. no implementation was produced ------------------------------------------------------
    expect(
        not list((ROOT / "migrations").glob("*delivery_review_task*")),
        "check43",
        "a delivery review task migration was created",
    )
    expect(
        not list((ROOT / "migrations").glob("*delivery_submission*")),
        "check44",
        "a delivery submission migration was created",
    )
    for text, label in ((d05, "D05"), (evidence, "evidence")):
        expect(
            re.search(r"(?i)(NOT STARTED|PAUSED|not created)", flat(text)) is not None,
            "check45",
            f"{label} does not record that implementation has not started",
        )
    expect(bool(evidence), "check46", "the CR1 evidence artifact is missing")
    expect(
        "production_executed_true_count: 0" in d05
        and "production_executed_true_count: 0" in evidence,
        "check47",
        "production_executed_true_count: 0 is not recorded",
    )

    print(f"  checks_run={checks_run}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] 66D-D05 binding; active := closed_at IS NULL, closed := closed_at IS NOT NULL;")
    print("       no DeliveryReviewTask lifecycle enum; submission-status mirroring forbidden;")
    print("       delivery_review_task_status planned/not implemented; AT MOST ONE active per")
    print("       delivery_submission_id with required-existence deferred; closed_at implies no")
    print("       decision; transitions deferred; ARCH1 mirroring superseded in place and DESIGN")
    print("       non-interchangeability preserved; exact 10-path scope; no implementation,")
    print("       migration or runtime change; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
