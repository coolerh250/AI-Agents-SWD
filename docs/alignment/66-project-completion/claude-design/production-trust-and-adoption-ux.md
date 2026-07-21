# Production Trust & Adoption UX — M6/M7 (Step 66ALIGN.1, Claude Design)

> Owner: Claude Design. The onboarding, trust, and approval experience needed to take the product to
> production readiness (M6) and rollout/adoption (M7). Analysis only.

## M6 — Production Readiness & Platform Hardening (experience)

The console must let operator / admin / security roles **confirm the platform is safe to run for
real** without the product surface degrading into an engineering console.

- **Real identity / session / CSRF (66S):** replace test-only header role simulation with real
  identity; sessions expire gracefully (no raw 401 dead-ends — a readable "please sign in again");
  role is authoritative server-side.
- **Governance elevated for readiness:** Safety Center + Audit Evidence become the review surface
  for readiness sign-off — human-readable evidence, hashes/ids under disclosure.
- **Platform Ops complete but still secondary:** the readiness/runtime/security posture pages are
  where they belong (Platform Ops, collapsed/badged); they support the readiness decision without
  becoming the product headline.
- **Readiness is a human review, not an auto-action:** an operator readiness sign-off is a recorded
  decision; it never triggers a production/external action by itself.

**M6 human decision point:** operator readiness review/sign-off (with full, readable evidence).

## M7 — Production Rollout & Adoption (experience)

The experience a first-time user meets, and the trust/approval UX for running for real.

### Onboarding / first-run

- A first-run/onboarding path that teaches the loop (Assign → … → Accept) in product language.
- **Empty-org states that teach**, not blank screens: "Assign your first piece of work to the AI
  team" leading into the real Create Task flow.
- First-run vs returning states; no keyboard traps; fully accessible.

### Trust

- The AI team is **legible and honest**: what it will and won't do automatically is stated plainly
  (calm safety posture carried through), so a new user trusts it because the boundaries are visible.
- Human-readable audit/history so a user can see what the team did and why.
- No dark patterns; no implied automation the system won't actually perform.

### Approval UX for production-affecting actions

- Every production-affecting or external action is **explicitly human-approved**, with full evidence
  shown before approval, and a clear consequence preview ("this will…"). This is the single most
  important trust surface for production.
- Approvals reuse the M3 approval queue; production-affecting ones carry the strongest confirmation
  and the clearest "what happens if I approve" copy.
- The safe-by-default posture (nothing runs automatically; production/external gated) remains
  visible right up to and including the approval moment.

## Pages / states (M6/M7)

- **Pages:** onboarding/first-run; empty-org states; help/trust surface; real Settings/Identity
  (66S); Governance elevated for readiness; production-action approval UX.
- **States:** first-run vs returning; empty-org vs populated; session valid/expired; readiness
  incomplete/ready; approval pending/approved/rejected.
- **Empty/error/loading:** teaching empty states; graceful session-expiry and production errors
  (readable, actionable — never a raw stack/JSON).

## Agent visibility & product-language

The team stays legible and trustworthy to a first-time user (team-visibility-model applied);
onboarding and trust copy in product language; safety explained as reassurance.

## Accessibility

Onboarding and approval flows fully accessible; consequence previews programmatically associated;
no keyboard traps in first-run.

## Product Owner validation (M6/M7)

```text
M6:
- Real identity/session (no test-only header simulation); graceful session handling.
- Safety hardened; audit readable; Platform Ops complete but secondary.
- Operator readiness sign-off is a recorded human review, not an auto production action.
M7:
- A new user can be onboarded and understand the AI team and the loop.
- Empty-org states teach the loop rather than showing blank screens.
- Every production-affecting/external action is explicitly human-approved with evidence + consequence
  preview; safe-by-default posture visible throughout.
```

## What must remain placeholder-only / gated

- Any integration/channel not hardened stays disabled/honest through M6.
- At M7, nothing in the *shipped* scope should remain placeholder; anything still gated is explicitly
  declared out of the production scope and labelled — not hidden.

## Statement

Design analysis only. No runtime code. No production action. No merge. No Codex authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
