# AT-M1 — Implementation Slice Handoff

> **Planning only. No slice below is authorized. Each requires its own explicit Product Owner
> authorization. AT-M2 has NOT started. `production_executed_true_count: 0`.**

This document exists so AT-M2 can begin from a specification rather than from a re-reading of the
architecture. Every slice names its contract source, its exit gate and what it must not do.

## 1. Slice dependency order

```text
AT-M2-BE1  ActorPrincipal / AgentProfile
     |
AT-M2-BE2  ProjectTeamMembership
     |
AT-M2-BE3  ConversationThread / TeamMessage
     |
AT-M2-BE4  TeamDecision / Handoff
     |
AT-M2-BE5  Collaboration APIs / events
     |
     +--> AT-M2-FE1  Team roster / presence
     +--> AT-M2-FE2  Project Workroom
     |
AT-M2-QA   Collaboration E2E
```

## 2. AT-M2-BE1 — ActorPrincipal / AgentProfile

```text
Contract        actor-principal-and-team-model.md sections 1-3
Deliverables    ActorPrincipal persistence (principal_id, principal_type, display_name, status);
                AgentProfile persistence (agent_id, principal_id, role, capabilities,
                tool_policy_profile ref, model_provider_ref, status)
Exit gate       four principal types are representable; an AgentProfile resolves to a principal;
                a runtime_agent principal cannot be given a TASK_ROLES role by any code path
MUST NOT        modify shared/sdk/tasks/rbac.py
                store a provider key, token or DSN in AgentProfile
                claim authenticated production identity
Invariants      INV-01
Risk            HIGH -- root entity of the model
```

## 3. AT-M2-BE2 — ProjectTeamMembership

```text
Contract        actor-principal-and-team-model.md section 4
Deliverables    membership persistence (project_id, agent_principal_id, functional_role,
                membership_state, joined_at, left_at)
Exit gate       a principal holds different functional roles on two projects; leaving preserves
                the row and past attribution
MUST NOT        treat membership as an execution record
                delete a departed member's row
Invariants      INV-02
Risk            LOW
```

## 4. AT-M2-BE3 — ConversationThread / TeamMessage

```text
Contract        collaboration-and-workroom-model.md sections 3-5
Deliverables    thread persistence; message persistence with sender_principal_id, the three
                recipient forms, parent_message_id, message_type, summary, artifact_refs,
                audit_ref
Exit gate       two distinct agent principals exchange addressed, threaded, persisted messages in
                one project thread; every message is audited; at least one recipient form is
                always set
MUST NOT        introduce any chain-of-thought / raw prompt / token-trace field
                anchor a thread on a Task alone
                modify task_messages or migration 030
Invariants      INV-04, INV-02
Risk            HIGH -- the schema is where the prohibition is either honoured or lost
```

## 5. AT-M2-BE4 — TeamDecision / Handoff

```text
Contract        collaboration-and-workroom-model.md sections 7-8
Deliverables    TeamDecision persistence (options_considered, selected_option, rationale_summary,
                dissent_summary, resulting_plan_revision_id); Handoff persistence with state
                machine offered -> accepted | declined | withdrawn | expired
Exit gate       a decision records options and preserved dissent; a handoff transfers ownership
                only on acceptance; a declined handoff leaves ownership unchanged
MUST NOT        share an enum with ProductOwnerDecision or Review Gate Actions
                map a TeamDecision value onto a delivery decision
                use a bare next_owner string
Invariants      INV-03
Risk            HIGH -- decision conflation is the most damaging possible error here
```

## 6. AT-M2-BE5 — Collaboration APIs / events

```text
Contract        collaboration-and-workroom-model.md section 5; layer L2 in at-m1-architecture-reset.md
Deliverables    commands (open_thread, post_message, propose, challenge, record_team_decision,
                offer_handoff, accept_handoff, raise_blocker, ask_clarification); durable events
                via the EXISTING transactional outbox pattern
Exit gate       an agent principal posts through the API and the event is durable; cross-project
                access is denied and masked as 404, matching the existing RBAC posture
MUST NOT        let an agent answer its own clarification
                bypass the outbox and publish inline
                change clarification expiry behaviour (AT-D09 is OPEN)
Risk            MEDIUM
```

## 7. AT-M2-FE1 / FE2 — Team roster, Project Workroom

```text
Contract        at-m1-architecture-reset.md section 3 (L2 read models); 66D-DESIGN-v2 amendment
                requirements
Deliverables    FE1 team roster and presence; FE2 project-scoped Team Workroom rendering threads,
                messages, proposals, challenges, decisions and handoffs
Exit gate       an operator can read a multi-agent conversation and see who decided what
MUST NOT        render or expose any reasoning-trace field (none exists -- the UI must not invent
                one from concatenated summaries)
                offer manual assignment as a normal affordance
                modify Delivery Review surfaces
Risk            MEDIUM
Note            depends on the 66D-DESIGN-v2 amendment, which is AT-M5 design work; FE slices may
                be sequenced after AT-M5 rather than inside AT-M2 if the Product Owner prefers
```

## 8. AT-M2-QA — Collaboration E2E

```text
Contract        functional-poc-capability-contract.md P01-P05
Deliverables    an end-to-end test proving >= 2 agent principals, one thread, >= 1 proposal,
                >= 1 TeamDecision, >= 1 accepted Handoff, all persisted and audited
Exit gate       the test asserts from the durable record, not from in-memory objects
MUST NOT        assert against templated fixture content
                use a single principal writing every role's message -- the exact defect
                agent_discussion has today
Risk            MEDIUM
```

## 9. Explicitly out of AT-M2 scope

```text
LLM-authored message content        AT-M3 (agents may post structured messages first)
Goal entity and PlanRevision        AT-M3
Dynamic dispatch                    AT-M3
DebugAttempt and the loop           AT-M4
Vector retrieval                    DEFERRED
Verified identity                   AT-M8
66D DeliverySubmission persistence  AT-M7 -- PR #28 is the input, still HELD
```

## 10. Preconditions for starting AT-M2

```text
1  AT-M1 merged to canonical main
2  AT-M1-R1 independent review passed
3  explicit Product Owner authorization for AT-M2
4  AT-D09 may remain OPEN -- AT-M2 does not depend on it
```

```text
AT-M2 has NOT started. AT-M1 authorizes nothing.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
