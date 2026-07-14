# Direction B — Agent Workspace

> Owner: Claude Design. One of three product visual/interaction directions for DESIGN-66UI.3. Not
> selected by default — see `product-owner-discussion-guide.md`.

1. **Direction name:** Agent Workspace.

2. **Design concept:** The single task and its Workroom are the product. Opening a task opens a
   workspace where the human and the AI team collaborate: conversation, the current decision being
   asked, the task's journey through stages, and (later) its delivery review all live together. The
   experience is "working alongside an AI team on this piece of work," and the Workroom is the
   emotional and functional center of gravity.

3. **Best suited users:** Requester, PM / Engineering Lead (on a specific task), Engineer — anyone
   doing deep single-task collaboration.

4. **Page layout model:** Left IA nav + calm safety strip; selecting a task opens a task workspace
   (conversation as the primary column, a context rail for task status / current decision / safety /
   delivery). Lower density than Direction A; focused on one task at a time.

5. **Navigation treatment:** Keep the 7 groups but treat the task list as the main doorway;
   everything else (Operator Center, Governance, Platform Ops) is a supporting destination.
   Platform Ops stays collapsed and quiet.

6. **Dashboard treatment:** Light. The landing is a personal "your tasks / what's waiting on you"
   list rather than an operational dashboard; a compact summary strip (decisions waiting,
   deliveries to review) sits above it. Cross-task operational views exist but are secondary.

7. **Workroom treatment:** The centerpiece and the biggest change from today. A real
   human–AI-team conversation: distinct, legible treatments for human vs. agent vs. system vs.
   clarification; agent identity and turn-taking; a prominent "the team is waiting on your decision"
   state; the current clarification rendered as a decision request at the top of the workspace, not
   as a log entry. Delivery review (66D) later becomes a tab in this same workspace. Plain-text
   bodies throughout.

8. **Safety / audit treatment:** A compact, task-scoped posture chip inside the workspace context
   rail ("This task: no automated actions, approval required, fully audited"), expandable to detail;
   the cross-task Safety Center and Audit Evidence remain their own calm pages. Reassurance-first,
   detail-on-demand.

9. **Operator Center treatment:** Secondary — present in the nav for operator roles, but this
   direction does not optimize for cross-task operations. Weakest of the three for Agent Operator.

10. **Visual tone:** Focused, calm, "workspace." Dark ground kept; the conversation surface gets the
    most design care (readable rhythm, clear authorship, comfortable line length); everything else
    recedes to support it.

11. **Pros:**
    - Directly fixes the highest-impact problem (the log-like Workroom) and most fully expresses the
      product's differentiator.
    - Best experience for the collaboration the product is *about*.
    - Naturally reinforces the Send-Message vs. Clarification distinction as adjacent, clearly
      different affordances.

12. **Cons:**
    - Weakest for Platform Admin / Agent Operator, whose work is inherently cross-task.
    - Larger front-end restructure (task detail + workroom converge toward one workspace) — needs
      its own implementation-plan review before Codex starts (already flagged in the 66UI.2 brief).
    - The Delivery tab ships empty/placeholder until 66D.

13. **Implementation risk:** Medium-high. The workspace convergence is the biggest structural change
    of the three; the Workroom message-treatment redesign is high-value but must preserve plain-text
    rendering and all safety semantics exactly.

14. **What should be redesigned first:** The **Workroom message treatment** (human/agent/system/
    clarification differentiation + agent identity + "waiting on you" state). It is the single
    highest-upside change and the truest to the product.

## Safety UX (mandatory, all directions)

Same guarantees as Direction A: `dispatch_enabled=false` / `resume_dispatch_enabled=false` /
`production_executed_true_count=0` shown server-computed and displayed-as-returned inside a calm
task-scoped posture chip (plus the cross-task Safety Center); `production_effect`,
external-action-disabled, approval-required, RBAC-denied, audit-restricted keep their semantics and
readable messages; no control implies dispatch/resume/production/external action.

## Statement

Design direction only. No runtime code. No production action. No Codex implementation authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
