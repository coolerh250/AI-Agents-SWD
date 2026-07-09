# AI Agents Team Work — Acceptance Criteria (Step 66A.3)

> **Blueprint / scope only. No implementation, no runtime change, no external action, no production
> action.** Acceptance is operator-owned — Claude Code does not decide product acceptance.

## 1. MVP acceptance criteria (per stage)

- **66B:** a manager assigns/creates + tracks a task from Console/API; RBAC create/view enforced.
- **66C:** the workroom shows agent messages + progress; a clarification pauses the task, a human
  reply resumes it; 24h reminder + 72h expiry behave; owner may extend once.
- **66D:** Accept / Reject / Request Changes (small→same, major→linked) / Re-run QA (≤3) / Escalate /
  Archive all work with correct transitions + audit; Approvals page and DLQ/Retry page operable;
  replay restricted to Admin/Agent-Op.
- **66E:** an assigned task runs the fixed Software Delivery Team and produces a reviewable delivery;
  task-type routing correct; `prod_exec=0`.
- **66F:** a task can be created via a controlled channel (Discord) with identity→role mapping +
  audit; unmapped identity rejected.
- **66G:** lifecycle events notify (Console P0 + Discord P1) with no sensitive data; Action Center
  aggregates all queues with RBAC.
- **66H:** the operator completes the full journey (assign → work → workroom → clarification →
  delivery → accept/request-changes → notifications → action center) with operator-visible evidence.

## 2. Cross-cutting acceptance invariants

- RBAC enforced server-side across all surfaces (D1).
- `production_executed_true_count=0` throughout; no production action; no unauthorized external write/
  send/LLM/web.
- Every mutating action audited; workroom↔audit correlation holds.
- Re-run-QA ≤3 (D12); replay Admin/Agent-Op only (D13); clarification timeout per D4.
- Web research not executed (no connector); whitelist v0.1 governance present as design.

## 3. Governance / definition of done

- Each stage: verifier PASS + pytest + ruff/black/mypy + secret scan (critical=0/high=0) + progress
  updated; commit+push; test-host deploy under explicit authorization.
- **Operator validation required per stage; the operator — not Claude Code — decides product
  acceptance.**

## Statement

Acceptance criteria only — no implementation, no runtime change, no external action, no production
action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
