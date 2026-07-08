# AI Agents Team Work — Web Research Source Whitelist Proposal (Step 66A.2)

> **Documentation only. This is a PROPOSED whitelist pending operator confirmation — NOT an approved
> final whitelist, and NOT evidence of live web research.**
> **No web browsing/search was performed. The runtime currently has no browsing/search connector.**

Operator decision **D10 = C (whitelist sources only)** requires web research to be governed by an
operator-approved source whitelist, and asked Claude Code to **propose a recommended top-10** for
review. This document is that proposal.

## Capability & governance caveats (must read)

- The current runtime has **no browsing/search connector** — this is a **missing capability**. No web
  browsing/search was performed to produce this list; sources are proposed from general knowledge.
- These 10 entries are **candidates pending operator approval**. Claude Code must not treat the
  whitelist as final.
- Web research must not run until an **approved browsing/search connector exists and is explicitly
  authorized** (a future controlled rail, off by default, budget + audit + citation — see
  `ai-team-work-web-research-capability-model.md`).
- No claim of "latest information collected" is made or implied.

## Proposed top-10 sources (operator approval pending)

| # | Source | Domain | Why useful | Task types supported | Risk / limitation | MVP whitelist? | Operator approval |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Anthropic Documentation | docs.anthropic.com | Claude/agent building, tool use, best practices | platform research, software delivery | vendor-specific | yes | **pending** |
| 2 | OpenAI Platform Docs | platform.openai.com | agent/LLM API patterns | platform research, software delivery | vendor-specific | yes | **pending** |
| 3 | Model Context Protocol | modelcontextprotocol.io | agent tool/connector standard | platform research, integration design | emerging spec, churn | yes | **pending** |
| 4 | LangChain / LangGraph Docs | python.langchain.com | agent orchestration frameworks | software delivery, research | framework churn, unofficial patterns | yes | **pending** |
| 5 | Microsoft Learn (Azure AI / AutoGen) | learn.microsoft.com | multi-agent frameworks + cloud AI | research, IT operations | vendor-specific | yes | **pending** |
| 6 | Google Cloud — Vertex AI Agents | cloud.google.com | cloud AI agent services | research, IT operations | vendor-specific | yes | **pending** |
| 7 | AWS — Bedrock Agents Docs | docs.aws.amazon.com | cloud AI agent services | research, IT operations | vendor-specific | yes | **pending** |
| 8 | OWASP (incl. GenAI / LLM Top 10, ASVS) | owasp.org | security review + governance references | security review, governance | advisory, not exhaustive | yes | **pending** |
| 9 | NIST — AI Risk Management Framework | nist.gov | governance / compliance references | governance, compliance review | US-centric, high-level | yes | **pending** |
| 10 | arXiv (cs.AI / cs.MA) | arxiv.org | AI / multi-agent research literature | research, platform research | **preprints — unvetted**, verify claims | yes (with caution) | **pending** |

## Source-category coverage

The proposal spans the operator-requested categories: official vendor documentation (1,2), official
API docs (2,3), security advisories (8), major cloud-provider AI-agent documentation (5,6,7),
recognized AI research organizations / literature (10), enterprise architecture references (5,6,7),
software supply chain / DevSecOps references (8), and governance / compliance references (8,9).

## Recommended governance for the whitelist (for 66A.3)

- Deny-by-default: only whitelisted domains reachable; blocklist overrides.
- Per-source metadata retained (retrieval time, URL) for citation + freshness.
- Human approval required when research **affects a decision**.
- arXiv (preprints) flagged as unvetted — require corroboration before use in a decision.

## Plain statements (for verifier)

- This is a proposed top-10 source whitelist pending operator confirmation.
- The final whitelist is not approved.
- No web browsing or search was performed; no live research was collected.
- The runtime lacks a browsing/search connector (missing capability); browsing capability is not
  fabricated.
- No production action occurred.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
