# AI Agents Team Work — Web Research Capability Model (Step 66A.1)

> **Planning / discovery only. No UI implementation. No external action. No production action.**
> **Current runtime has NO web browsing / search connector — recorded as a missing capability, not fabricated.**

Operator decision **D2** requires tasks that can **collect and analyze the latest online information
related to the AI Agents Team Work platform.** This model defines the requirement and governance; it
does **not** claim the capability exists today.

## 1. Capability gap (explicit)

- The agent pipeline today has **no browsing / web-search connector**. "Latest online info" tasks are
  **not currently executable**.
- This is a **future connector requirement** (capability gap), not an existing feature. No web
  capability is assumed or fabricated.

## 2. Requirements for a future web research connector

| Aspect | Requirement |
| --- | --- |
| web research tool | a governed search/fetch connector (allowlisted), off by default |
| source citation | every claim carries source URL + retrieval timestamp |
| freshness policy | record retrieval time; flag stale sources; prefer recent |
| allowed / blocked domains | explicit allowlist / blocklist; deny by default |
| privacy rules | no PII/customer data in queries; no secrets in queries or logs |
| cost / quota control | per-task and global quotas; budget policy like the LLM rail |
| human approval | when research **affects a decision**, require human approval before it is used |
| evidence storage | store fetched evidence + citations with the delivery |
| delivery format | research brief: summary, findings, citations, freshness, confidence |

## 3. Governance alignment

- Modeled on the Step 65 controlled-rail pattern (off by default; explicit per-use authorization;
  budget + audit). A live web connector would be a **new controlled rail**, enabled only under
  explicit operator authorization — never on by default.
- Until such a connector is authorized and built, research/market-analysis task types are **flagged
  blocked** in the task taxonomy.

## 4. Note on this environment

- This planning was produced **without** performing any live web research for the platform's product
  decisions; where "latest online info" would be needed, it is marked as a connector requirement.

## 5. Statement

No web/browsing/search action was performed. No external action occurred. No production action
occurred. The connector is a future requirement, not a current capability.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
