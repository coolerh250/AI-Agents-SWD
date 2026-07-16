# Overview Information Architecture — DESIGN-66UI.4-FE.1C

> Owner: Claude Design. The attention-first information hierarchy for the Overview page. Order =
> priority: the top of the page answers "what needs me," the bottom holds reference metrics.

## Hierarchy (top → bottom)

```text
A. Page header
   - Title: "Overview" (product-level; replaces "Executive Overview")
   - One-line purpose: what this page helps you do

B. Needs your attention            ← highest priority
   - Human decisions/inputs the AI team is waiting on
   - Real items from existing task data; honest placeholders for 66D/66C.4 items
   - Never fabricated counts

C. AI team activity
   - What the AI team is doing now / recently (existing agent-execution data)
   - Product-readable status, not raw backend labels

D. Current work snapshot
   - Recently updated / active tasks (existing task data)

E. System posture (summary + link)
   - One calm line reusing FE.1B posture output; link to Safety / Governance
   - Does NOT duplicate FE.1B detail

F. Platform & delivery metrics      ← demoted (today's 12 cards live here)
   - Existing getOverview() cards, secondary, collapsible/below-the-fold

G. Future capabilities              ← lowest; honest placeholders
   - Delivery Review (66D), Reminder/Expiry (66C.4), Notifications/Action Center (future),
     Pipeline (future, read-only only)
```

## Priority rationale

- **B before everything**: the reason a person opens the app is to see what the AI team needs from
  them. This is the single biggest change from today (where metrics lead).
- **C and D** give situational awareness (Direction A command-center framing) without dense tables.
- **E** keeps safety visible but calm and non-duplicative (FE.1B owns the detail).
- **F** preserves all current data, demoted — nothing is lost, it just stops leading.
- **G** sets honest expectations about what's coming without implying it works.

## Visual weighting (uses FE.1A tokens + Phase 1 visual-language)

- Section B action items that are non-zero/need-action use the raised/attention surface; zero/clear
  states stay calm. Reference metrics (F) use the quiet surface. No new tokens introduced.
- Attention conveyed by treatment + text label, never color alone (accessibility).

## Role-awareness

The Overview is the same page for all roles; role-based landing (66UI.2) still routes some roles
elsewhere (e.g. Agent Operator → Operator Center). Section content is governed by server-side RBAC
on the underlying endpoints — the Overview does not gate access client-side, and shows honest empty
states where a role's data returns nothing.

## What the IA does not add

No new nav item, no route change, no new endpoint. FE.1C restructures the content of the existing
`/` Overview route only.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
