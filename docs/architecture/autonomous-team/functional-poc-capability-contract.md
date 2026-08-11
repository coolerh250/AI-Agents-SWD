# Autonomous Team — Functional POC Capability Contract

> **Architecture contract only. Nothing here is implemented. This document defines what would have
> to be TRUE for a POC to be called functional; it does not claim any of it is true today.
> `production_executed_true_count: 0`.**

Target milestone: **AT-M6**. Implements AT-D04 and the L1–L5 boundaries.

## 1. Purpose

"Functional autonomous team POC" must be a testable claim, not a demo impression. This contract is
the acceptance definition. Every clause below is observable from durable evidence, so the claim can
be verified from the record rather than from watching it run.

## 2. Required capabilities

All of the following must hold in a single end-to-end run:

```text
P01  >= 3 runtime agents participate, each an ActorPrincipal with a distinct functional role
P02  persisted multi-agent discussion -- >= 2 distinct sender principals in one thread
P03  >= 1 proposal recorded
P04  >= 1 TeamDecision recorded, naming options considered and the selected option
P05  >= 1 Handoff offered by one principal and accepted by another
P06  a plan GENERATED from the Goal (not selected from a fixed template list)
P07  >= 1 PlanRevision beyond revision 1, with a reason and a diff against its predecessor
P08  ownership assigned dynamically -- every work item has an owner and an assignment reason
P09  real files generated in a sandboxed workspace
P10  real tests executed -- a genuine test runner process, not a recorded status
P11  an intentional failure occurs and is detected by verification
P12  the failure is diagnosed -- a DebugAttempt with a hypothesis
P13  an autonomous fix is applied -- artifact or plan changed by an agent
P14  re-test PASSES after the fix
P15  a delivery artifact is produced
P16  complete audit lineage: Goal -> Plan -> Work Item -> Run -> Artifact -> QA -> Delivery,
     every hop attributable to a principal
P17  NO manual assignment occurred
P18  NO manual next-step occurred
```

## 3. Permitted human actions during the POC run

```text
set the goal
answer a clarification
approve a policy-gated high-risk action
inject a correction
halt
accept or reject the final delivery
```

```text
Any human action outside this list INVALIDATES the POC run.
It is recorded as an intervention and the run is reported as PASS_WITH_INTERVENTION or FAIL,
never silently as PASS.
```

P17 and P18 are the sharp ones. A run in which an operator assigned one agent or clicked one
"next" is a supervised workflow demo, and calling it autonomous would be the exact
false-complete this programme exists to avoid.

## 4. Evidence requirements

Each clause maps to durable evidence, verifiable after the run:

| Clause | Evidence |
| --- | --- |
| P01 | >= 3 `ProjectTeamMembership` rows, `principal_type = runtime_agent`, distinct functional roles |
| P02 | one `ConversationThread` with `TeamMessage` rows from >= 2 distinct `sender_principal_id` |
| P03 | `TeamMessage.message_type = proposal` |
| P04 | `TeamDecision` with non-empty `options_considered` and `selected_option` |
| P05 | `Handoff` with `state = accepted` and `from != to` |
| P06 | `PlanRevision` revision 1 whose work items are not equal to the template fixture's nine |
| P07 | `PlanRevision` revision >= 2 with `reason` and `supersedes_revision_id` set |
| P08 | every work item has `owner_principal_id` and `assignment_reason` |
| P09 | artifact rows with content hashes and a non-empty diff |
| P10 | a test-run record with a real command, exit code and output summary |
| P11 | a QA finding or failing test recorded from the run |
| P12 | `DebugAttempt` with `hypothesis_summary` and `failure_ref` |
| P13 | artifact change or `PlanRevision` authored by an agent principal, linked to the attempt |
| P14 | a later test run for the same work item with a passing status |
| P15 | a delivery artifact / submission record |
| P16 | an unbroken audit chain across all seven hops |
| P17 | zero ownership assignments whose `assignment_reason` is a human override |
| P18 | zero human-issued advance/next/retry commands in the run window |

## 5. Explicitly NOT required for the POC

```text
verified production identity          RA-2 / AT-M8
production deployment                 AT-M8
GitHub write / real PR                deferred
external delivery / notifications     deferred
vector retrieval / semantic memory    DEFERRED (AT-D: shared context is relational)
multi-project concurrency             already partially implemented; not a POC gate
Helm / ArgoCD / Vault                 currently .gitkeep only; not a POC gate
CI pipeline                           currently absent; not a POC gate
66D DeliverySubmission persistence    PR #28; the POC may deliver via the legacy path
full 66D-DESIGN-v2 UX                 AT-M5 surfaces are needed to OBSERVE the POC, not to run it
```

```text
PR #28 is USEFUL_BUT_NOT_REQUIRED for the POC and remains HELD / NON-CANONICAL.
```

## 6. Minimum blocking capability set

Derived from the audit and re-verified at this baseline. In dependency order:

```text
B1  a real LLM/reasoning capability, wired and enabled
        today: no LLM SDK in requirements.txt; the only real provider is plan-only and gated off
B2  goal decomposition producing a generated plan
        today: a hard-coded nine-item Python list
B3  an agent-addressable, threaded message primitive with >= 2 participating agents
        today: zero recipient fields; no runtime agent writes a message
B4  dynamic dispatch + conditional routing
        today: static YAML mapping; a linear LangGraph with no conditional edges
B5  test-driven verification feeding diagnosis
        today: QA evaluates static rules; the auto-fix path has three hard-coded buckets
```

```text
B1..B5 are POC-BLOCKING. Everything in section 5 is not.
```

## 7. POC scenario shape (illustrative, not prescriptive)

```text
1  human sets a Goal with acceptance criteria and constraints
2  planner principal decomposes it into a PlanRevision; the team discusses and records a decision
3  work is owned dynamically; a backend principal generates real files in a sandbox
4  a qa principal runs real tests; one fails (intentionally seeded)
5  the qa principal opens a DebugAttempt and hands the item to a backend principal
6  the backend principal applies a fix, re-executes; tests pass
7  the team prepares a delivery artifact
8  a human accepts or rejects it
```

```text
Steps 2-7 involve NO human action. Steps 1 and 8 are the only required human involvement.
```

## 8. Verification

AT-M6 must ship an automated verifier that reads the durable record of a run and asserts P01–P18
plus the section 3 constraint. A POC whose success depends on a person describing what they saw is
not verified.

## 9. Dependencies

```text
Requires    AT-M2 (principals, collaboration), AT-M3 (planning, dispatch), AT-M4 (execution,
            debug loop); AT-M5 for observation surfaces
Blocked by  B1..B5
Status      CONTRACT_ONLY / NOT IMPLEMENTED
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
