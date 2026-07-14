# Product Owner Decision Record — DESIGN-66UI.2

> Owner: Claude Design (recording the Product Owner's verdict and decisions). Binding scope
> reference for the open questions raised in `product-owner-review-checklist.md`. This record does
> not authorize Codex implementation.

## Verdict

```text
READY_FOR_CODE_REVIEW
```

The Product Owner (Zachary) accepts the DESIGN-66UI.2 Navigation / IA Detailed Design for Claude
Code architecture review. Draft PR #2 stays **open and draft — do not merge**.

## Decisions on the open questions

### 1. Dashboard vs Operational Metrics — do NOT merge this round

- Dashboard remains the Overview landing page.
- Operational Metrics remains separate under Platform Ops (`/metrics`) for now.
- **Effect on docs:** matches the brief as written; no change required.

### 2. DeliveryPackage ownership — keep under Deliveries (CHANGES the brief)

- Keep `DeliveryPackage` under the **Deliveries** group as the existing delivery evidence / package
  record.
- Do **not** merge it with Delivery Inbox yet; final integration waits for the Step 66D API / data
  contract.
- **Effect on docs:** this **overrides** the brief's original placement (which had `Delivery
  Package` under Platform Ops). `navigation-map.md`, `page-grouping.md`, and
  `migration-from-current-nav.md` are updated in the same commit as this record so the design set is
  consistent with this decision before Claude Code reviews. `DeliveryPackage` becomes the one
  **active** (existing, working) item in the Deliveries group, sitting alongside the 66D
  placeholders (Delivery Inbox, Delivery Detail) and clearly distinct from them.

### 3. Deliveries empty group — show with safe placeholders

- Show the Deliveries group in the nav shell, with safe placeholders for the unfinished pages.
- Placeholder pages must clearly state: "Not yet available", "Requires Step 66D", "No workflow
  action available".
- **Effect on docs:** matches `placeholder-rules.md` and the decision above (the group is no longer
  empty — it has the active `Delivery Package` plus compliant 66D placeholders). No rule change
  required; open question #3 is resolved.

### 4. Security / Compliance cross-group access — acceptable

- The Security / Compliance Reviewer may enter from Governance / Safety Center and access
  audit/safety-related views across groups where server-side RBAC allows.
- The frontend must not become the authority for access control.
- **Effect on docs:** matches `role-based-entry-points.md`; no change required.

### 5. Notifications scope — in-app only

- First version is in-app notifications only.
- External Slack / Discord / Telegram notification behavior is out of scope for this IA shell.
- **Effect on docs:** matches the brief (Notifications marked in-app only; external channels
  "Coming later"); no change required.

## Authorization status

- Codex remains **unauthorized** to implement until Claude Code completes the architecture review
  **and** the Product Owner explicitly authorizes the first frontend implementation stage.
- Next step: Claude Code executes **Step 66UI.2-R — Navigation / IA Architecture Review**.

## Statement

Design specification / decision record only. No runtime code. No production action. No Codex
implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
