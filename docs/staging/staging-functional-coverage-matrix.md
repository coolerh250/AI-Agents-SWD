# Staging Functional Coverage Matrix (Step 65A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Read-only assessment / documentation only — no runtime change, no workflow execution, no integration enablement in this stage.**

Inventory of "all functions" of the AI Agents Platform and each capability's current **staging**
status on `10.0.1.32`. This is an honest, read-only classification — most agent/workflow evidence
so far is **seeded/mock**, not a fresh end-to-end run, and live external integrations are
disabled/mocked.

## Status values
`STAGING_VALIDATED` · `TEST_VALIDATED_ONLY` · `SEEDED_EVIDENCE_ONLY` · `MOCKED` · `DISABLED` ·
`NOT_IMPLEMENTED` · `UNKNOWN` · `BLOCKED_BY_CREDENTIAL` · `BLOCKED_BY_AUTHORIZATION` ·
`BLOCKED_BY_DESIGN`

## Classification fields (per item)
domain · capability · current staging status · evidence source · mock/real/disabled/seeded ·
required external resource · requires credential · requires operator authorization · requires user
visual validation · acceptance criteria · blocking gap · recommended step · priority

## A. Intake & request lifecycle
| Capability | Staging status | Evidence source | mode | ext resource | cred | op-auth | visual | blocking gap | step | prio |
|---|---|---|---|---|---|---|---|---|---|---|
| Mock intake (`/workflow/test`) | SEEDED_EVIDENCE_ONLY | Step 64D seed | seeded | none | no | no | no | not a real intake | 65G | high |
| Communication-gateway intake (`/intake/mock/project-work-item`) | BLOCKED_BY_DESIGN | Step 64D (500, gateway PyYAML) | disabled | none | no | no | no | gateway image missing PyYAML | 65G | high |
| Operator-submitted task path | BLOCKED_BY_AUTHORIZATION | operator_actions_disabled | disabled | none | no | yes | yes | operator actions gated in staging | 65G/65H | med |
| Work item creation (WI-0001) | SEEDED_EVIDENCE_ONLY | delivery seed | seeded | none | no | no | yes | seeded, not workflow-created | 65G | high |
| Project association / evidence creation | SEEDED_EVIDENCE_ONLY | delivery seed | seeded | none | no | no | yes | seeded | 65G | med |

## B. Agent pipeline
| Capability | Staging status | Evidence | mode | blocking gap | step | prio |
|---|---|---|---|---|---|---|
| intake / requirement / development / qa / devops agents | SEEDED_EVIDENCE_ONLY | 10 agent executions from mock workflow | mock | not a fresh run; mock agents | 65G | high |
| orchestrator dispatch | SEEDED_EVIDENCE_ONLY | mock workflow | mock | mock path only | 65G | high |
| stream events (11 streams active) | STAGING_VALIDATED (infra) | `/operations/streams` count=11 | real | events not exercised by a new run | 65G | med |
| agent execution persistence | SEEDED_EVIDENCE_ONLY | `/operations/agent-executions` count=10 | seeded | seeded rows | 65G | med |
| stage completion | SEEDED_EVIDENCE_ONLY | mock workflow completed | mock | mock | 65G | med |

## C. Workflow orchestration
| Capability | Staging status | Evidence | blocking gap | step | prio |
|---|---|---|---|---|---|
| workflow creation / persistence | SEEDED_EVIDENCE_ONLY | `/operations/workflows` count=2 | seeded/mock | 65G | high |
| workflow resume | TEST_VALIDATED_ONLY | test suite | not exercised in staging | 65H | med |
| workflow cancel / abort / ignore-after-abort | TEST_VALIDATED_ONLY | test suite | not exercised in staging | 65H | high |
| workflow state visibility | STAGING_VALIDATED | Task Graph page (operator-accepted) | — | — | — |
| workflow trace in Admin Console | STAGING_VALIDATED | 64E.4D acceptance | — | — | — |

## D. QA / code / workspace evidence
| Capability | Staging status | Evidence | blocking gap | step | prio |
|---|---|---|---|---|---|
| QA runs / validation runs | SEEDED_EVIDENCE_ONLY | `/operations/qa/runs` count=2 | seeded | 65G | med |
| code workspace records / output evidence | SEEDED_EVIDENCE_ONLY | `/operations/code/workspaces` count=2 | seeded | 65G | med |
| workspace lifecycle | TEST_VALIDATED_ONLY | test suite | not a fresh staging run | 65G | med |
| formal QA / Code UI visibility | STAGING_VALIDATED | 64E.4D acceptance | — | — | — |

## E. Audit / evidence / compliance
| Capability | Staging status | Evidence | blocking gap | step | prio |
|---|---|---|---|---|---|
| audit events / work-item events | SEEDED_EVIDENCE_ONLY | `work_item_created` event | seeded | 65G | med |
| audit integrity (HMAC / keyring) | TEST_VALIDATED_ONLY | test suite + Stage 42 history | not re-verified in staging | 65H | med |
| operator action audit | BLOCKED_BY_AUTHORIZATION | operator actions disabled | disabled | 65H | med |
| evidence trail / Admin Console audit visibility | STAGING_VALIDATED | Audit/Evidence page accepted | — | — | — |

## F. Governance / approval / safety
| Capability | Staging status | Evidence | blocking gap | step | prio |
|---|---|---|---|---|---|
| policy engine / approval engine (running) | STAGING_VALIDATED (infra) | services healthy | paths not exercised | 65H | med |
| human approval required / granted / denied / expired paths | TEST_VALIDATED_ONLY | test suite | not exercised in staging | 65H | high |
| operator action gating | STAGING_VALIDATED | `operator_actions_disabled` observed | — | — | — |
| production action blocking | STAGING_VALIDATED | `production_executed_true_count=0` | — | — | — |
| Safety Center | STAGING_VALIDATED | 64E.4D acceptance | — | — | — |

## G. Retry / failure / DLQ / recovery
| Capability | Staging status | Evidence | blocking gap | step | prio |
|---|---|---|---|---|---|
| agent failure simulation | TEST_VALIDATED_ONLY | test suite | not exercised in staging | 65H | high |
| retry scheduler (service running) | STAGING_VALIDATED (infra) | container healthy | logic not exercised | 65H | med |
| dead letter queue (`stream.deadletter[.terminal]`) | STAGING_VALIDATED (infra) | streams present | not exercised | 65H | high |
| manual replay / terminal failure state | TEST_VALIDATED_ONLY | test suite | not exercised in staging | 65H | med |
| cancel / abort / failure evidence visibility | TEST_VALIDATED_ONLY | test suite | not exercised in staging | 65H | high |

## H. External integrations
| Integration | Staging status | mode | ext resource | cred | op-auth | step |
|---|---|---|---|---|---|---|
| GitHub sandbox repo | MOCKED / BLOCKED_BY_CREDENTIAL | dry-run (has mock token; external write off) | sandbox repo | yes | yes | 65D |
| Slack / Discord staging channel | DISABLED | no token (`discord_has_token=false`) | test channel/webhook | yes | yes | 65E |
| LLM staging key | MOCKED | `llm_provider=mock`, external call off | non-prod key + quota | yes | yes | 65F |
| Secret backend (Vault-like) | MOCKED | `secret_provider=mock-vault` | staging secret store | yes | yes | 65C |
| Container registry sandbox | NOT_IMPLEMENTED | none | sandbox registry | yes | yes | 65B/65D |
| Notification sandbox | DISABLED | none | test channel | yes | yes | 65E |
| Cloud storage / Drive (if in scope) | UNKNOWN | none | tbd | tbd | tbd | 65B |

Per-integration detail (kill switch, allowed/forbidden, audit) →
[staging-integration-readiness-assessment.md](staging-integration-readiness-assessment.md).

## I. Admin Console / operator experience
| Capability | Staging status | Evidence | gap |
|---|---|---|---|
| formal product pages | STAGING_VALIDATED | 64E.4D operator PASS | — |
| operator workflow visibility | STAGING_VALIDATED | 64E.4D | — |
| Safety Center / Operational Metrics | STAGING_VALIDATED | 64E.4D | — |
| Release Governance | STAGING_VALIDATED (read-only) | governance gated | actions disabled by design |
| diagnostics page policy | STAGING_VALIDATED | Demo Evidence diagnostic-only | — |
| SPA deep-link 404 | KNOWN_GAP (accepted) | 64F.2/64F.3 | non-blocking; navigate via tabs |

## J. Deployment / operations
| Capability | Staging status | Evidence | gap |
|---|---|---|---|
| restart rehearsal | STAGING_VALIDATED | 64F.2 | — |
| rebuild/redeploy rehearsal | STAGING_VALIDATED | 64F.3 | — |
| stop/start rehearsal | NOT_IMPLEMENTED (not yet rehearsed) | — | 64F.4 (paused) |
| rollback rehearsal | NOT_IMPLEMENTED (not yet rehearsed) | — | future 64F |
| restore rehearsal | NOT_IMPLEMENTED (not yet rehearsed) | — | future 64F |
| backup / DR relationship | TEST_VALIDATED_ONLY | DR docs/endpoints | not exercised in staging |

## Summary (counts are indicative, see gap register)
- **STAGING_VALIDATED:** Admin Console formal pages, Safety Center, operator/production gating,
  workflow/audit visibility, restart + rebuild/redeploy rehearsals, stream/service infra.
- **SEEDED_EVIDENCE_ONLY / MOCKED:** the whole intake→agent→workflow→QA→code→audit data path (seeded
  via mock, not a fresh end-to-end run).
- **TEST_VALIDATED_ONLY:** resume/cancel/abort, approval paths, retry/DLQ/replay, audit integrity —
  proven in tests, not in staging.
- **DISABLED / BLOCKED:** communication-gateway intake (PyYAML), operator actions, live
  GitHub/Discord/LLM, registry sandbox.
- **Biggest blockers to staging functional acceptance:** (1) no fresh end-to-end workflow from a real
  intake; (2) live external integrations not set up (credentials + sandbox resources + operator
  auth); (3) failure/governance paths not exercised in staging.

## Posture
Read-only assessment only. No runtime change, no workflow execution, no integration enablement, no
secret creation, no production action; `production_executed_true_count=0`. Step 64F.4 is paused;
this is the Step 65 functional-validation track. This does not imply production readiness. Claude
Code does not decide staging functional acceptance.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
