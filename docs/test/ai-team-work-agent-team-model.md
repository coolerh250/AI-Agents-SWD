# AI Agents Team Work — Agent Team Model (Step 66A.1)

> **Planning / discovery only. No UI implementation. No production action.**

Operator decision **D6: MVP uses a fixed Software Delivery Team first**; full custom composition is
out of MVP scope. This model defines the fixed MVP team and the future team-selection roadmap.

## 1. Fixed Software Delivery Team (MVP)

| Agent | Role in pipeline |
| --- | --- |
| `intake-agent` | receives task, normalizes request |
| `requirement-agent` | derives requirements / spec |
| `development-agent` | produces implementation (sandbox) |
| `qa-agent` | runs QA / verification |
| `devops-agent` | packaging / delivery (sandbox draft PR) |

This matches the Step 65-validated pipeline (`intake→requirement→development→qa→devops`). MVP does
**not** allow changing this composition.

## 2. Future team selection roadmap (post-MVP)

```
Phase 1: fixed Software Delivery Team            (MVP — 66E)
Phase 2: selectable team templates                (later)
Phase 3: role-based custom team composition        (later)
Phase 4: AI-suggested team composition             (later)
```

## 3. Non-software task → future team mapping (modeled, not built)

| Task family | Future team (Phase 2+) | Extra agents needed |
| --- | --- | --- |
| Research / web analysis | Research Team | research agent + **web connector (missing)** |
| IT operations | Ops Team | workspace-operator, devops |
| Security review | Security Team | security/compliance review agent |
| Data / knowledge analysis | Analysis Team | data-analysis agent |

These are **not** in MVP. MVP keeps the fixed team; non-software task types wait for templates
(decision item **D14**).

## 4. Boundaries (decision item D6)

- MVP fixed-team scope boundaries (what the team will/won't attempt) require operator confirmation.
- Recommendation (NON-FINAL): MVP fixed team handles software-delivery / documentation /
  platform-improvement tasks only; other task types return "not supported by current team".

## 5. Statement

No team composition was implemented or executed. No external action occurred. No production action
occurred. Future phases are recommendations only.

## Recorded decision (66A.2)

**D6 = B** — the fixed Software Delivery Team covers **software delivery, documentation, and platform
improvement**; other task types are accepted at intake/planning level but enter the **intake/research
queue** and do not run the full delivery pipeline until future templates exist. **D14 = B** — MVP UI
offers task-type selection; non-software tasks route to intake/planning/documentation first. Future
phases (templates → role-based → AI-suggested composition) remain out of MVP.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
