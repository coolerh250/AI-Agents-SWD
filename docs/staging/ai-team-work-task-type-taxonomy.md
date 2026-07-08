# AI Agents Team Work — Task Type Taxonomy (Step 66A.1)

> **Planning / discovery only. No UI implementation. No production action. MVP priorities are non-final and require operator review.**

Operator decision **D2: support all AI-agent-capable tasks** (not software-only), including
**web research for latest AI-Agents-Team-Work-related information**. This taxonomy defines task types
and a **recommended** MVP priority. Final priority is decision item **D2**.

## 1. Task types

| Task type | Inputs required | Agents involved | Tools / external access | Approval gates | Delivery artifact | Risk | MVP priority (proposed) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Software delivery | requirement/spec | full fixed team | repo (sandbox), CI (dry-run) | governed writes | draft PR + QA report | med | **P0 (MVP)** |
| Documentation generation | topic/source | requirement, development, qa | repo docs | none/low | doc artifact | low | **P1** |
| Research / web analysis | question, scope | requirement, (research)* | **web connector (missing)** | research-affects-decision | research brief + citations | med | P1 (blocked on connector) |
| IT operations | runbook/target | devops, workspace-operator | ops APIs (scoped) | production-block | ops result | high | P2 |
| Security review | artifact/scope | qa, sec-review | scanners | sign-off | findings report | high | P2 |
| Incident analysis | incident ref | devops, qa | logs/metrics | none/low | RCA report | med | P2 |
| Data / knowledge analysis | dataset ref | development, qa | data access (scoped) | privacy | analysis report | med | P2 |
| Business process automation | process spec | full team | integrations | production-block | automation + doc | high | P3 |
| Platform improvement task | improvement spec | full team | repo (sandbox) | governed writes | draft PR | med | P1 |
| AI Team Work market/tech research | research scope | requirement, (research)* | **web connector (missing)** | research-affects-decision | market/tech brief | med | P1 (blocked on connector) |

`*` a dedicated research agent + web connector does not exist today (capability gap; see
`ai-team-work-web-research-capability-model.md`).

## 2. MVP scope recommendation (NON-FINAL)

- **MVP (66E) executes only via the fixed Software Delivery Team.** Software delivery, documentation
  generation, and platform-improvement tasks map cleanly onto it and are the recommended first scope.
- Non-software task types (IT ops, security review, research, etc.) are **modeled now but deferred**
  to future team templates (decision item **D14**), because the fixed team + missing connectors do not
  yet cover them safely.
- Web-research task types are **flagged blocked** on the web connector requirement — not fabricated as
  available.

## 3. Statement

No task was executed. No external action occurred. No production action occurred. MVP priorities are
recommendations only and require operator review (D2).

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
