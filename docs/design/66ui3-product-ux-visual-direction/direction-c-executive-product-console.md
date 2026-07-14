# Direction C — Executive Product Console

> Owner: Claude Design. One of three product visual/interaction directions for DESIGN-66UI.3. Not
> selected by default — see `product-owner-discussion-guide.md`.

1. **Direction name:** Executive Product Console.

2. **Design concept:** A deliberately simplified, product-grade surface that any role can use
   without engineering fluency. Engineering detail (ops, evidence, raw fields, Platform Ops) is
   pushed to a clearly secondary layer; the primary surface speaks entirely in product language and
   shows only what a person needs to make progress. The bet: the fastest way to stop feeling
   "engineering" is to *remove* engineering detail from the primary layer, not just restyle it.

3. **Best suited users:** Cross-role, including non-technical stakeholders and executives who want
   status and outcomes without operational depth; friendly to Requester and PM.

4. **Page layout model:** Left IA nav (Platform Ops and Operator tooling visibly demoted to a
   "second layer"); main area is a clean, low-density product dashboard and a small set of primary
   flows (assign work, track a task, answer a decision, review a delivery). Highest whitespace,
   lowest density of the three.

5. **Navigation treatment:** Two visual tiers: a **primary** tier (Overview, Team Work, Deliveries,
   Governance-summary) and a **secondary/advanced** tier (Operator Center, Platform Ops, full
   Governance/Audit, Settings) that is present but visually subordinate (e.g. a separated
   "Advanced / Operations" section). Same routes as 66UI.2; only visual weighting changes.

6. **Dashboard treatment:** The most simplified — a small number of large, plain-language status
   tiles ("3 decisions waiting for you," "2 deliveries ready to review," "All systems safe — nothing
   runs automatically"). Numbers-with-meaning, not metric grids. Deep metrics move to the secondary
   layer.

7. **Workroom treatment:** Clean and conversational, but lighter than Direction B — enough to read
   as a human-AI conversation (clear authorship, the decision surfaced), without a heavy
   workspace build. Plain-text bodies.

8. **Safety / audit treatment:** Reassurance-first and prominent-but-calm: a single plain-language
   safety statement on the primary layer ("No automated or production actions will run. Everything
   is recorded."); the detailed fields and audit evidence live in the secondary Governance layer for
   those who need them.

9. **Operator Center treatment:** Demoted to the secondary/advanced layer. Present and fully
   functional for operators, but it does not shape the primary product feel at all. Weakest operator
   prominence of the three (by design).

10. **Visual tone:** Polished, approachable, "product." This direction most invites revisiting the
    palette — likely a lighter or dual-theme option and more whitespace — to break hardest from the
    engineering aesthetic. The most visual risk and the most visual upside.

11. **Pros:**
    - Most directly answers "make it feel like a product, not engineering" for the widest audience.
    - Lowest cognitive load; best for non-technical stakeholders and demos.
    - Cleanly honors the PO decision that Platform Ops must not dominate the product feel.

12. **Cons:**
    - Risks hiding detail that operators/PMs genuinely need day-to-day (two-tier nav can frustrate
      power users).
    - The biggest departure from the current look — highest visual-design churn and the most new
      decisions (palette/theme) required before build.
    - If the "simplification" removes governance visibility from where users expect it, it can
      weaken the auditable-by-default story.

13. **Implementation risk:** High. Requires the most new visual-design decisions (palette, possibly
    theme, density system) and a two-tier nav treatment; more surface area for regressions and the
    most review cycles. Still no backend/API change — but the largest front-end visual effort.

14. **What should be redesigned first:** The **design language + palette/token system and the
    primary dashboard** — because this direction's whole premise is a new product-grade visual
    layer; getting the tokens and the simplified dashboard right is the prerequisite for everything
    else.

## Safety UX (mandatory, all directions)

Same guarantees: `dispatch_enabled=false` / `resume_dispatch_enabled=false` /
`production_executed_true_count=0` remain server-computed and displayed-as-returned — here surfaced
as a single plain-language reassurance on the primary layer with full detail one layer down;
`production_effect`, external-action-disabled, approval-required, RBAC-denied, audit-restricted keep
their semantics and readable messages; no control implies dispatch/resume/production/external
action. Simplification must never *remove* a safety signal — only relocate detail while keeping the
plain-language guarantee visible.

## Statement

Design direction only. No runtime code. No production action. No Codex implementation authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
