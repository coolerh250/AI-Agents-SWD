# Recommendation — DESIGN-66UI.1

> Owner: Claude Design. This is a recommendation for Product Owner discussion, **not** a final
> decision. Per the stage prompt: do not proceed to high-fidelity design until the Product Owner
> confirms an option (or hybrid, or another round).

## Recommended option

**Option 1 — Operations Command Center**, as the starting point, with Option 2's tabbed-workspace
pattern folded in when a task is opened (the hybrid sketched in `layout-comparison.md`).

## Why recommended

1. **Lowest migration risk for the highest-certainty win.** The clearest, least-debatable problem
   found in this pass is the 27-item flat nav (`Nav.tsx`) — Option 1 fixes that directly with the
   least frontend rework, and does not require any 66D/66C.4 backend work to land value
   immediately.
2. **Does not foreclose Options 2 or 3.** Because Option 1 is primarily an IA/navigation change,
   nothing about it prevents layering Option 2's tabbed task workspace or Option 3's pipeline board
   in as a Team Work sub-view later — see `layout-comparison.md` "Hybrid possibility."
3. **Matches current dependency reality.** Delivery (66D) and Reminder/Expiry (66C.4) are not yet
   built. Option 1 is the only option whose core value does not depend on either — Options 2 and 3
   both have a component that ships empty/placeholder without them.
4. **Lower risk of the two failure modes the stage prompt warns against.** A disciplined card
   dashboard is easier to keep from reading as either "chatbot" or "plain issue tracker" than a
   Kanban board (Option 3's stated risk) — Option 1's risk (NOC-dashboard sprawl) is more directly
   within Claude Design's control to mitigate at the component-spec stage.

This recommendation is not unconditional — if the Product Owner's actual priority is proving out
the single-task collaboration experience (Workroom) as the product's signature differentiator
*before* investing in cross-task operator tooling, Option 2 is the more honest choice even though
it costs more to build. See the discussion questions below.

## What to discuss with the Product Owner

1. Is the near-term priority operational scale (many concurrent tasks, Agent Operator workload) or
   single-task collaboration depth (Workroom experience quality)? This is the single question that
   most determines Option 1 vs. Option 2.
2. Is Category H (the pre-existing ~20-page Platform Operations/DevOps Governance surface) in
   scope for this redesign at all, or should it be left alone for now regardless of which option is
   chosen?
3. Should the pre-existing `DeliveryPackage.tsx`/multi-project delivery model be merged with the
   new Task-linked Delivery Inbox (66D), or are they genuinely two different concepts (release-
   level vs. task-level delivery)?
4. Is a Kanban-style pipeline (Option 3) something the Product Owner actually wants eventually,
   even if not chosen now — worth flagging so it isn't lost, since it's the option most tied to the
   product's "fixed Software Delivery Team" framing.
5. Any appetite for the hybrid (Option 1 nav + Option 2 task workspace), or should this stay a
   strict pick-one to keep scope contained for the first redesign pass?

## What should not be implemented yet

- No layout choice authorizes any Codex frontend work yet — this stage produces options only.
- No component from any option (nav shell, task workspace tabs, pipeline board, drawer) should be
  built until the Product Owner responds via `product-owner-discussion-guide.md`.
- No decision here changes API/contract behavior — Claude Code's contract work is not triggered by
  this document.
- The Category H scope question should not be silently resolved by omission — it needs an explicit
  answer, not a default.

## Impact on Codex frontend work

- **Can start now:** nothing — this stage is options-only, pending Product Owner selection.
- **Once an option is selected**, the lowest-risk first PR regardless of choice is the nav-shell
  change (Option 1's grouped `NavGroup`, or the equivalent minimal nav for Option 2/3) — it touches
  no business logic and can ship ahead of any 66D/66C.4-dependent component.
- **Must wait on 66D:** Delivery-related components in all three options (Deliveries list, Delivery
  tab, Review column) cannot be meaningfully built until Claude Code's Delivery contract exists.
- **Must wait on 66C.4:** Any "overdue/reminder" indicator (Action Center badge, board blocked-
  swimlane trigger) depends on the reminder/expiry scheduler's data shape.

## Impact on Claude Code / API-contract work

- **No contract change is requested by this document.** This stage does not ask Claude Code to
  produce or modify any `docs/contracts/<stage>/` artifact.
- **If Option 3 is chosen**, a specific question needs a contract-level answer before Codex can
  build the board: is task stage purely server-derived and read-only in the UI, or can a user
  request a manual stage transition? That answer belongs to Claude Code/product, not to this
  design pass.
- **If a hybrid or Option 2 is chosen**, no new contract is implied beyond what 66D/66C.4 already
  plan to deliver — this is a frontend/IA restructuring, not a new data requirement.
- **Safety/governance impact:** none of the three options change any safety posture — all three
  keep `dispatch_enabled`/`resume_dispatch_enabled`/`production_executed_true_count` equally
  visible; this redesign does not touch backend safety enforcement in any way.

## Open questions

See `product-owner-discussion-guide.md` for the consolidated list with the required response
format.

## Statement

Design specification only. No runtime code. No production action. No API/contract decision. No
Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
