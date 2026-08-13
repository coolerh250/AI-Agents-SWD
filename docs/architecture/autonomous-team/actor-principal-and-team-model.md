# Autonomous Team — Actor Principal and Team Model

> **Architecture contract only. No entity in this document exists in the codebase. No runtime,
> backend, API, frontend, database, migration, identity or secret change.
> `production_executed_true_count: 0`.**

Implements AT-D02. Machine-verified starting position: `ActorPrincipal`, `principal_id`,
`AgentProfile` and `ProjectTeamMembership` have **zero** occurrences on canonical main.

## 1. What an actor is

An **ActorPrincipal** is the answer to "who or what did this". It is the single subject that can
originate a message, own a work item, appear in an audit record, or be handed work.

Today the platform answers that question four different ways — an `actor_ref` string, an
`X-Task-Actor` header, an agent service name, and a `created_by_agent` column. Those cannot be
joined, cannot be authorized against, and cannot be listed. One abstraction replaces them.

```text
principal_id      stable opaque identifier
principal_type    human | runtime_agent | ai_partner | system
display_name      human-readable, safe to render
status            active | suspended | retired
```

### Capabilities by principal type

| | authenticate | own work | send messages | appear in audit | hold TASK_ROLES |
| --- | --- | --- | --- | --- | --- |
| `human` | yes (session) | yes | yes | yes | **yes** |
| `runtime_agent` | no (logical only) | yes | yes | yes | **never** |
| `ai_partner` | no (logical only) | yes | yes | yes | **never** |
| `system` | no | no | yes (system events) | yes | **never** |

"Authenticate" here means *establishes a verified identity*. A runtime agent has a logical
principal so its actions are attributable; that is not the same as being authenticated, and
section 5 states the boundary explicitly.

## 2. Four concepts that must not collapse (D02-R5)

```text
Human authentication identity   a verified session belonging to a person
    != ActorPrincipal           the abstraction covering humans AND non-humans
    != TASK_ROLES               what a HUMAN is permitted to authorize
    != Agent functional role    what an agent is FOR
    != ProjectTeamMembership    which project a principal is currently working on
```

Worked example. `qa-agent` running on project P:

```text
ActorPrincipal          principal_type=runtime_agent, principal_id=<opaque>
AgentProfile            role=qa, capabilities={run_tests, diagnose_failure}
ProjectTeamMembership   project P, functional_role=qa, membership_state=active
TASK_ROLES              NONE -- and it must never acquire one
Authentication          NONE -- it is a logical principal
```

It can run tests, post findings, be handed work and appear in the audit trail. It cannot approve
anything, because approval is a human authorization act evaluated against `TASK_ROLES`.

## 3. AgentProfile

The functional identity of a runtime agent — what it is for, and what it may reach.

```text
agent_id                  identity of the profile
principal_id              the ActorPrincipal this profile describes
role                      functional role (backend, frontend, qa, planner, reviewer, devops, ...)
capabilities              declared capability set, e.g. {generate_code, run_tests, diagnose,
                          propose_plan, review}
tool_policy_profile       REFERENCE to a policy profile naming permitted tools and boundaries
model_provider_ref        REFERENCE to a provider/model configuration
status                    active | disabled | retired
```

```text
MUST NOT contain a provider API key, token, DSN or any secret VALUE.
`tool_policy_profile` and `model_provider_ref` are references resolved at runtime by the existing
secret-reference machinery; the profile stores the name, never the material.
```

`capabilities` is what the dynamic dispatcher matches against. It is declarative, and a capability
being declared is not permission to exercise it — the tool policy profile and L5 policy still
apply.

## 4. ProjectTeamMembership

Answers "who is on this team", which is a different question from "who did this work".

```text
project_id                the team's project
agent_principal_id        the member (any principal type, despite the field name's emphasis)
functional_role           the role this principal plays ON THIS PROJECT
membership_state          invited | active | paused | left
joined_at
left_at                   nullable
```

```text
Membership is NOT an execution record. It says a principal is available to the team, not that it
did anything. Execution stays on Work Item -> Run (AT-D01).
```

A principal may hold different functional roles on different projects. Membership is historical:
leaving sets `left_at` rather than deleting the row, so a past decision by a departed member stays
attributable.

## 5. Security boundary (hard)

```text
An ActorPrincipal identifier is a LOGICAL principal.
It does NOT imply an authenticated production identity.
```

```text
Today          sandbox / internal test runtime operator identity; request-supplied actor and role
               fields (X-Task-Actor / X-Task-Role) are NEVER authoritative
Future         verified human identity and workload identity, owned by RA-2 and AT-M8
NOT CLAIMED    production authentication, workload attestation, or non-repudiation
```

AT-M1 must not describe production authentication as complete, and no AT-M2 slice may either. The
honest statement is: attribution improves immediately, authentication does not change at all.

### Preserved

```text
TASK_ROLES = {requester, pm_engineering_lead, reviewer_approver, platform_admin, agent_operator,
              security_compliance_reviewer}
```

Exactly six, unchanged, human-only. `agent_operator` is a **human who operates agents**, not an
agent — a distinction the naming makes easy to lose, and INV-01 exists to protect.

## 6. Relationship to existing entities

```text
operator_tasks.created_by / owner        human string -> future: principal reference
agent_executions.agent_name              service name -> future: AgentProfile reference
task_messages.sender_type / sender_id    already close in shape; gains principal_id
audit records actor_ref                  redacted actor -> future: principal reference
ARCH1 actor contract (section 7)         PRESERVED; ai_partner classification is compatible
```

Migration of those fields is AT-M2-BE1 work and is deliberately not specified here beyond the
mapping. No column is renamed by AT-M1.

## 7. Dependencies

```text
Requires    nothing -- ActorPrincipal is the root of the AT entity graph
Enables     ProjectTeamMembership, TeamMessage addressing, Ownership, Handoff, DebugAttempt
            attribution
Blocked by  nothing
Slice       AT-M2-BE1
Status      CONTRACT_ONLY / NOT IMPLEMENTED
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
