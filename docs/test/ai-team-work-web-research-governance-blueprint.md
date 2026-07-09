# AI Agents Team Work — Web Research Governance Blueprint (Step 66A.3)

> **Blueprint / scope only. No implementation. NO web research was performed. The runtime has NO
> approved browsing/search connector. Browsing capability is not claimed to exist.**
> **Q4 confirmed: approved source whitelist v0.1 (D10 whitelist-only).**

## 1. Approved source whitelist v0.1 (operator-confirmed)

| # | Source | Note |
| --- | --- | --- |
| 1 | OpenAI Developers / Agents SDK | vendor docs |
| 2 | Anthropic Claude Platform Docs | vendor docs |
| 3 | Model Context Protocol Docs | protocol/standard |
| 4 | LangGraph / LangChain Docs | framework |
| 5 | Microsoft Agent Framework / Microsoft Learn | vendor/cloud |
| 6 | Google Gemini Enterprise Agent Platform / Vertex AI Agent Builder | vendor/cloud |
| 7 | AWS Bedrock Agents / AgentCore | vendor/cloud |
| 8 | OWASP Gen AI Security / LLM Top 10 | security |
| 9 | NIST AI RMF / GenAI Profile | governance/compliance |
| 10 | arXiv | **preprint warning — unvetted, corroborate before use** |

This is **whitelist v0.1**, operator-approved as the starting set; changes go through the source
approval workflow.

## 2. Governed capability requirements (design; not implemented)

- **Connector requirement:** a governed browsing/search connector must be **built and explicitly
  authorized** before any web research runs. It does not exist today (missing capability).
- **Source whitelist enforcement:** deny-by-default; only whitelisted domains reachable; blocklist
  overrides.
- **Source approval workflow:** Platform Admin proposes/edits sources; Security/Compliance reviews;
  changes audited.
- **Search request model:** typed query + task link + purpose; quota-checked before dispatch.
- **Citation model:** every claim carries source URL + **retrieval timestamp**.
- **Freshness policy:** record retrieval time; flag stale; prefer recent.
- **Cost / quota control:** per-task + global quotas (budget-policy pattern like the LLM rail).
- **Human review requirement:** when research **affects a decision**, require human approval before use.
- **Blocked source handling:** non-whitelisted request rejected + audited; no silent fallback.
- **Evidence storage:** fetched evidence + citations stored with the delivery.
- **Delivery integration:** research output appears as a cited research brief in the delivery package.
- **Audit event:** every request/citation/approval emits an audit event.

## 3. MVP posture

Web research is **not executed in MVP** — it is designed here as a future controlled rail (off by
default, per-use authorization). Research/market-analysis task types remain **flagged blocked** until
the connector is built + authorized. No web research capability is claimed to exist.

## Statement

Web research governance blueprint only. No web/browsing/search action performed; no external action; no
production action. Whitelist v0.1 is operator-approved as a starting set; the connector is future work.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
