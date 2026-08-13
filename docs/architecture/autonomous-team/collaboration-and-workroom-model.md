# Autonomous Team — Collaboration and Workroom Model

> **Architecture contract only. Nothing here is implemented. No runtime, backend, API, frontend,
> database, migration or event change. `production_executed_true_count: 0`.**

Implements AT-D03. Machine-verified starting position: `shared/` contains **zero** recipient or
addressing fields, and no runtime agent writes a `task_messages` row.

## 1. The problem being fixed

`shared/sdk/agent_discussion/` produces rows that look like a discussion and contain none.
`REVIEW_MODES = ("deterministic_template", "llm_assisted_disabled", "human_review")` has no live
mode; every role's "contribution" is a hard-coded English string, and a single agent
(`design-review-agent`) authors all of them. No second participant exists.

That module is a **fixture**, and this contract supersedes it as the collaboration model. It is not
deleted — see section 8.

## 2. Scope promotion

```text
BEFORE   Workroom is scoped to a Task. Participants are humans. Agents are described, not present.
AFTER    Team Workroom is scoped to a Project/Goal. Runtime agents are first-class participants.
```

The scope change is what makes collaboration possible at all: work is planned per Goal and executed
per Work Item, so a task-scoped room can never hold a conversation about the plan.

```text
Team Workroom scope   project_id (required) + goal reference
Optional narrowing    work_item_id, run_id -- a thread ABOUT a work item or a run
Never                 a thread whose only anchor is a Task (AT-D01: no second execution lineage)
```

## 3. ConversationThread

```text
thread_id
project_id                required
goal_ref                  required -- the Goal this conversation serves
work_item_id              nullable -- present when the thread is about one work item
run_id                    nullable -- present when the thread is about one run (e.g. a failure)
thread_type               planning | design | execution | debug | blocker | clarification |
                          handoff | decision
state                     open | resolved | superseded | archived
created_at
```

A thread is resolved when its question is answered, not when it goes quiet. `superseded` exists so
a thread replaced by a later one (e.g. after a replan) stays readable with its successor named.

## 4. TeamMessage

```text
message_id
thread_id                     required
sender_principal_id           required -- an ActorPrincipal of any type
recipient_principal_id        nullable -- addressed to one principal
recipient_role                nullable -- addressed to a functional role (e.g. "qa")
recipient_team                nullable -- addressed to the whole project team
parent_message_id             nullable -- explicit threading; a reply names its parent
message_type                  see section 5
summary                       short, safe, reviewable conclusion
content                       structured body per message_type, redacted
artifact_refs                 references to artifacts, runs, plan revisions, QA evidence
audit_ref                     the audit event recording this message
created_at
```

At least one of `recipient_principal_id`, `recipient_role`, `recipient_team` is set. An unaddressed
message is a broadcast to the team and must say so explicitly rather than by omission — the absence
of a recipient is exactly the ambiguity that makes today's streams uncollaborative.

### The storage prohibition (D03-R8, hard)

```text
FORBIDDEN FIELDS -- must not exist in any schema, DTO, event payload, projection or export:
    private_chain_of_thought        raw_system_prompt
    hidden_reasoning                reasoning_tokens / token_trace
    private_scratchpad              unredacted_prompt
    secret / credential values
```

```text
PERMITTED -- durable collaboration evidence:
    summary                 proposal content         decision rationale summary
    question / answer       hypothesis summary       result summary
    artifact_refs           audit_ref
```

The line is between a conclusion a principal stands behind and the process that produced it. The
first is reviewable evidence and belongs in the team record. The second is not reviewable, not
safe to retain, and no field may be designed to hold it. INV-04 verifies this mechanically.

## 5. Message type semantics

| type | who may produce | who may consume | durable | changes state | human action | audit |
| --- | --- | --- | --- | --- | --- | --- |
| `message` | any principal | thread participants | yes | no | no | yes |
| `proposal` | any principal | thread participants | yes | no | no | yes |
| `challenge` | any principal | proposal author + team | yes | no | no | yes |
| `decision_summary` | any principal | team | yes | **yes** — points at a TeamDecision | no | yes |
| `handoff` | current owner | target principal | yes | **yes** — ownership pending | no | yes |
| `blocker` | any principal | team + L1 | yes | **yes** — may set BLOCKED | maybe | yes |
| `clarification_question` | agent principal | human | yes | **yes** — may set WAITING_FOR_HUMAN | **yes** | yes |
| `clarification_answer` | human only | thread participants | yes | **yes** — clears the wait | no | yes |
| `debug_hypothesis` | diagnosing principal | team | yes | no | no | yes |
| `debug_result` | diagnosing principal | team | yes | **yes** — feeds DebugAttempt | no | yes |
| `replan` | planner principal | team | yes | **yes** — new PlanRevision | no | yes |
| `system_event` | `system` only | team | yes | no | no | yes |
| `audit_event` | `system` only | team + auditors | yes | no | no | yes |

```text
clarification_answer is HUMAN-ONLY. An agent answering its own clarification would make the
clarification loop decorative.
```

Every row is audited. A collaboration record that is not attributable is not evidence.

## 6. Proposal / challenge / consensus

```text
propose      a principal states an option and its rationale summary
challenge    another principal states an objection, with its own rationale summary
converge     the team records ONE TeamDecision naming the selected option, the options considered,
             and any dissent that was not resolved
```

```text
Consensus is NOT required for a decision to be recorded.
Unresolved dissent is RECORDED, not suppressed (`dissent_summary`).
```

A model that requires agreement stalls; a model that hides disagreement is worse than no record. A
decision that carries its dissent is reviewable later, which is the point.

## 7. TeamDecision

```text
decision_id
project_id
thread_id                     the conversation that produced it
proposed_by                   principal
options_considered            the alternatives, each with a summary
selected_option
rationale_summary             why -- a conclusion, never a reasoning trace
dissent_summary               nullable -- unresolved objections, preserved
resulting_plan_revision_id    nullable -- set when the decision changed the plan
created_at
```

### Separation (D03-R6, INV-03)

```text
TeamDecision           coordination / technical choice made BY the team
Approval               policy authorization granted BY a human with TASK_ROLES capability
ProductOwnerDecision   delivery acceptance made BY the Product Owner
```

```text
The three MUST NOT share enums.
The three MUST NOT substitute for one another.

A TeamDecision does NOT authorize a production action.
A TeamDecision does NOT replace human approval.
A TeamDecision does NOT replace Product Owner acceptance.
```

`TeamDecision` values are free-form selected options, not an enum drawn from
`{ACCEPTED, ACCEPTED_WITH_FOLLOW_UP, REJECTED}` or the six Review Gate Actions. Any mapping between
them is forbidden: it would let a team accept its own delivery.

## 8. Handoff

First-class, because "who owns this now" is the question a `next_owner` string cannot answer
honestly — it cannot express an offer that was declined, or a transfer still pending.

```text
handoff_id
project_id
work_item_id
from_principal_id
to_principal_id
reason                    why the work is moving
context_refs              artifacts, runs, threads the receiver needs
state                     offered | accepted | declined | withdrawn | expired
created_at
accepted_at               nullable
```

```text
A bare `next_owner` string MUST NOT be used as the handoff mechanism.
Ownership transfers on `accepted`, not on `offered`.
```

## 9. Relationship to existing substrate

```text
task_messages (migration 030)   PRESERVED. Task-scoped human/agent messaging stays exactly as it
                                is. AT collaboration does not migrate or repurpose it.
agent_discussion (Stage 46)     SUPERSEDED AS THE COLLABORATION MODEL. It remains a valid
                                deterministic review FIXTURE and its rows stay readable. It must
                                not be described as multi-agent participation, and it is not the
                                autonomous control path.
clarification contracts (66C.4) PRESERVED UNCHANGED, including expiry. AT-D09 is OPEN.
```

Two message substrates coexisting is deliberate and bounded: `task_messages` serves the human task
surface, Team Workroom serves the project/goal team. AT-D01 forbids a second *execution* lineage;
it does not forbid a second *conversation* surface, provided only the project-scoped one drives
autonomous work.

## 10. Dependencies

```text
Requires    ActorPrincipal, ProjectTeamMembership
Enables     dynamic dispatch (needs handoff + decisions), replanning (needs decision provenance)
Slices      AT-M2-BE3 (thread/message), AT-M2-BE4 (decision/handoff), AT-M2-BE5 (APIs/events)
Status      CONTRACT_ONLY / NOT IMPLEMENTED
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
