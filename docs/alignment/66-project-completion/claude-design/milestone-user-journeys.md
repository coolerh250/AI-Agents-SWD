# Milestone User Journeys — Step 66ALIGN.1 (Claude Design)

> Owner: Claude Design. The required 10-point analysis for each milestone M0–M7. M1/M2/M4/M6–M7 are
> expanded further in their dedicated companion docs. Every surface is anchored to a milestone; no
> ownerless fake feature is designed.

The 10 points per milestone: (1) Primary user journey · (2) Required pages · (3) Required states ·
(4) Empty/error/loading states · (5) Human decision points · (6) Agent visibility requirements ·
(7) Product-language requirements · (8) Accessibility · (9) PO validation checklist · (10) What must
remain placeholder-only.

---

## M0 — Source of Truth and Runtime Reconciliation

1. **Journey:** operator opens the console and everything shown truthfully reflects the deployed
   runtime — no surface implies a capability that isn't live.
2. **Pages:** no new pages; audit existing Overview, Safety, nav, placeholders for truthfulness.
3. **States:** "available", "not yet available (with stage)", "read-only/evidence" — all honest.
4. **Empty/error/loading:** confirm the already-shipped calm empty/error/role-restricted copy is
   consistent everywhere; no raw 404/500 leaking as product state.
5. **Human decision points:** none new — this is a reconciliation milestone.
6. **Agent visibility:** confirm agent-execution evidence is labelled as evidence, not implied
   live orchestration.
7. **Product-language:** no `snake_case`/raw-field regressions; placeholders honest.
8. **Accessibility:** confirm focus/labels/contrast baseline holds after FE.1A–FE.1D-S1.
9. **PO checklist:** every nav item's state matches runtime reality; no fake capability; safety
   posture accurate; placeholders name the correct gating stage.
10. **Placeholder-only:** Delivery, Reminder/Expiry, Approvals, DLQ/Retry, Notifications, Settings —
    all remain placeholder until their milestone.

---

## M1 — Core Human–Agent Interaction Loop  *(see `core-loop-experience-definition.md`)*

1. **Journey:** Assign → Converse → Clarify → Wait/Resume → Observe the AI team on this task.
2. **Pages:** Create Task; Task list; **Task Workspace** (Task Detail + Workroom as a product-grade
   collaboration surface); Clarification as a decision request within it.
3. **States:** task lifecycle (draft/intake/in-development/clarification-needed/waiting/…); message
   authorship (human/agent/system/clarification); **"the team is working" / "waiting on your
   answer" / "paused — will not resume automatically"** states.
4. **Empty/error/loading:** empty Workroom ("Start a discussion or ask the AI team a question");
   loading skeletons; role-restricted; safe wait state (not an error).
5. **Human decision points:** answer a clarification (the primary decision); send a message;
   submit/assign a task.
6. **Agent visibility:** which agent is acting, its state, turn-taking; "waiting on you" surfaced at
   the top, not buried in a log.
7. **Product-language:** "Ask the AI team for a decision" vs "Send a message"; "Answer recorded";
   "Answering won't automatically restart the team — a person decides the next step."
8. **Accessibility:** message authorship not by color alone; decision request keyboard-reachable;
   live-region for new messages where appropriate.
9. **PO checklist:** can assign; can converse; can raise + answer a clarification; the task's
   blocked/waiting state is unmistakable; no implication that answering auto-dispatches/resumes.
10. **Placeholder-only:** Delivery tab (until M2); workflow *resume* stays disabled/safe-stated until
    explicitly authorized; multi-agent orchestration controls (M3).

---

## M2 — Delivery and Acceptance Loop  *(see `delivery-experience-definition.md`)*

1. **Journey:** delivered work appears → reviewer opens it → Accept / Reject / Request Changes /
   Re-run QA.
2. **Pages:** Delivery Inbox (cross-task queue); Delivery Detail (acceptance desk).
3. **States:** delivery lifecycle (submitted/under-review/accepted/rejected/changes-requested/
   qa-rerun-requested); per-delivery QA + risk state.
4. **Empty/error/loading:** empty inbox ("Nothing to review right now."); loading; role-restricted;
   safe "no action will dispatch" reassurance.
5. **Human decision points:** Accept; Reject; Request Changes (small vs major); Re-run QA — the four
   decisions, each with clear consequence.
6. **Agent visibility:** which agent produced the delivery; QA agent result; what a re-run would do.
7. **Product-language:** acceptance-desk language, not JSON/evidence-dump; evidence is expandable
   secondary detail.
8. **Accessibility:** the four actions are distinct, labelled, keyboard-reachable; destructive/
   consequential actions confirmed.
9. **PO checklist:** can see deliveries awaiting review; can open one and understand it without
   reading raw JSON; can Accept/Reject/Request-Changes/Re-run-QA; the difference between Request
   Changes and Re-run QA is unambiguous.
10. **Placeholder-only:** anything requiring workflow re-dispatch stays gated until authorized;
    external delivery notifications (M4).

---

## M3 — AI Team Orchestration and Multi-role Control

1. **Journey:** operator/PM oversees multiple agents and roles across tasks; approver acts on gated
   actions; project/team scoping governs visibility.
2. **Pages:** Operator Center becomes real (Approvals queue, DLQ/Retry); Settings → Roles &
   Permissions, Identity/Session (66S); project/team scope.
3. **States:** approval lifecycle (pending/approved/rejected/expired); retry/DLQ state; per-role
   visibility; multi-agent team state.
4. **Empty/error/loading:** empty approval queue ("Nothing needs approval."); DLQ empty; RBAC-denied
   readable.
5. **Human decision points:** approve/reject a gated action; retry/replay/mark-terminal; assign
   roles.
6. **Agent visibility:** the full team's activity across tasks (see `team-visibility-model.md`);
   which agent is blocked/failed and why.
7. **Product-language:** "Needs approval before anything runs"; "Needs recovery" (DLQ); role names
   in product terms.
8. **Accessibility:** queues navigable; approval consequences explicit; server-side RBAC is the
   authority (nav visibility is convenience only).
9. **PO checklist:** approver has a real landing queue; operator can recover failures safely; roles
   govern what each user sees/does; no client-only RBAC.
10. **Placeholder-only:** real workflow dispatch/resume remains gated unless explicitly authorized;
    external channels (M4).

---

## M4 — Notifications, Action Center and Channels  *(see `action-center-channel-experience.md`)*

1. **Journey:** a user is told what needs them without hunting; in-app first, external channels
   later.
2. **Pages:** Notification Center (in-app feed); Action Center (aggregated actionable queue).
3. **States:** unread/read; actionable/informational; per-channel connected/disabled.
4. **Empty/error/loading:** "You're all caught up"; channel-not-connected.
5. **Human decision points:** act on an item from the Action Center; (later) configure a channel.
6. **Agent visibility:** notifications reference the agent/task that raised them.
7. **Product-language:** "N need your attention"; never raw event ids as the headline.
8. **Accessibility:** notification badges carry text; feed navigable.
9. **PO checklist:** in-app notifications work; Action Center aggregates real items; external send is
   clearly not active until authorized.
10. **Placeholder-only:** Slack/Discord/Telegram send stays placeholder/disabled until authorized;
    no external action implied.

---

## M5 — Controlled End-to-End Pilot

1. **Journey:** one real task taken through the entire loop (Assign→…→Accept) under controlled,
   guard-railed conditions.
2. **Pages:** the M1+M2 surfaces used together; a pilot-scope indicator.
3. **States:** pilot-active; guardrails-on; safe-by-default posture visible throughout.
4. **Empty/error/loading:** pilot not started; pilot task in each loop state.
5. **Human decision points:** every loop decision, end to end, once.
6. **Agent visibility:** full team activity for the pilot task.
7. **Product-language:** clearly a *controlled* pilot; nothing implies production.
8. **Accessibility:** full-loop keyboard path; no dead ends.
9. **PO checklist:** a user completes Assign→Accept once, end to end, with safety posture intact and
   no production/external action.
10. **Placeholder-only:** anything not exercised by the pilot; production rollout controls (M7).

---

## M6 — Production Readiness and Platform Hardening  *(see `production-trust-and-adoption-ux.md`)*

1. **Journey:** operator/admin/security confirms the platform is safe to run for real — identity/
   session/CSRF real (66S), safety hardened.
2. **Pages:** Governance (Safety/Audit) elevated for readiness review; Platform Ops readiness views;
   Settings/Identity real.
3. **States:** readiness gates; identity/session real; safety posture authoritative.
4. **Empty/error/loading:** readiness incomplete vs ready; session expiry handled gracefully.
5. **Human decision points:** operator readiness review/sign-off (not a production auto-action).
6. **Agent visibility:** audit trail of team actions is human-readable evidence.
7. **Product-language:** reassurance-first safety; readiness stated plainly.
8. **Accessibility:** governance surfaces meet the same bar as product surfaces.
9. **PO checklist:** real identity/session; safety hardened; audit readable; Platform Ops stays
   secondary but complete for readiness.
10. **Placeholder-only:** any not-yet-hardened integration stays disabled/honest.

---

## M7 — Production Rollout and Adoption  *(see `production-trust-and-adoption-ux.md`)*

1. **Journey:** new users onboard, trust the AI team, and adopt the loop in production.
2. **Pages:** first-run/onboarding; empty-org states; help/trust surfaces; approval UX for
   production-affecting actions.
3. **States:** first-run vs returning; empty-org vs populated; trust/consent captured appropriately.
4. **Empty/error/loading:** brand-new org empty states that teach the loop; graceful production
   errors.
5. **Human decision points:** onboarding steps; approving production-affecting actions with full
   evidence.
6. **Agent visibility:** the AI team is legible and trustworthy to a first-time user.
7. **Product-language:** onboarding in product terms; trust/safety explained plainly.
8. **Accessibility:** onboarding fully accessible; no keyboard traps.
9. **PO checklist:** a new user can be onboarded, understand the AI team, and complete the loop; all
   production-affecting actions are explicitly human-approved.
10. **Placeholder-only:** nothing should remain placeholder at M7 for the shipped scope; anything
    still gated is explicitly out of the production scope and labelled.

## Statement

Design analysis only. No runtime code. No production action. No merge. No Codex authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
