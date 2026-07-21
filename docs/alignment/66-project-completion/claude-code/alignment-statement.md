# Alignment Statement — Step 66ALIGN.1-CC

> **Analysis and documentation only. No implementation, merge, deployment, or runtime modification
> performed by this document.**

## Canonical milestone order — no conflict

No disagreement with the canonical order (`M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7`) or with
FE.1D-S2 being excluded from the critical path. This is recorded explicitly per the instruction not
to silently rewrite the order: **none found; the order matches the actual dependency structure in
the codebase** (see milestone-dependency-plan.md §2 for the reasoning per transition).

## Special questions — direct answers

### 是否應在 FE.1D-S1 後暫停 cosmetic work?

**Yes, recommend pausing further Admin-Console-only cosmetic work (FE.1D-S2 and beyond) as the
default execution priority after FE.1D-S1**, redirecting the next stage's capacity to 66C.4. This is
not a claim that FE.1D-S2 is bad work — its boundary and slicing plan are sound, low-risk, and
ready to execute whenever wanted — it is a claim that **cosmetic polish does not advance the
critical path while 66C.4 sits READY_TO_START**, and continuing to sequence cosmetic stages ahead
of it is the single clearest inefficiency this alignment review found (risk-register.md #1). If the
Product Owner has a specific reason to prioritize FE.1D-S2 anyway (e.g. an imminent stakeholder
demo that needs the polish), that is a valid product call this document does not override — but it
should be a deliberate choice, not a default continuation of the FE.1A→FE.1D-S1 sequencing
momentum.

### Step 66C.4 與 Step 66D 哪個應先開始，依賴關係是什麼?

**66C.4 first.** Dependency: M2 (66D)'s acceptance gate presumes tasks can actually reach a
completed/deliverable state through a real interaction loop, and 66C.4 is the one piece of that
loop (the clarification-timeout/reminder path) not yet built. There is no reverse dependency —
66D does not need anything from 66C.4 beyond "the interaction loop being complete" — but building
66D first would mean designing an acceptance gate around a task lifecycle that is still missing one
of its own status-transition paths, risking downstream rework in 66D once 66C.4's real behavior
becomes clear. 66C.4 is also lower-risk and faster (see technical-critical-path.md), so there is no
efficiency argument for reordering it either.

### Delivery data model/API 是否需要先於 UI 設計凍結?

**Yes, categorically.** This project has a strong, consistent precedent for this: every FE.1x stage
had a Claude-Code-owned contract/boundary document (`docs/contracts/<stage>/`) produced BEFORE
Codex implemented, and Claude Design was never authorized to modify runtime code or invent API
behavior. The 66D delivery/acceptance data model is significantly more consequential to get wrong
than any FE.1x label choice — it touches a real task's terminal state, a 6-action decision gate with
RBAC implications, and (eventually) real external notification of that decision. Freezing it via an
explicit `66D-ARCH` stage (see recommended-next-stages.md) before any UI design begins is the
direct, unambiguous recommendation. Designing the UI first and retrofitting the data model to match
whatever the design implies would invert this project's own established, successful pattern.

### 何時才適合啟動 Kubernetes/ArgoCD production substrate?

**Not before M5 (the controlled E2E pilot) has run and been validated**, and ideally not until M1-M4
are demonstrably real end-to-end. Concretely: **M6 is the correct milestone for this, per the
canonical order, and this analysis found no reason to pull it earlier.** Two supporting reasons
specific to this project's own history: (1) the Stage 60–63A work already built substantial
dry-run-only groundwork (deployment-authorization-boundary-model, production-credential-readiness-
model, production-gitops-readiness-model) in a non-production `kind`/ArgoCD sandbox — this is
valuable, reusable preparation, and can continue to be refined in parallel at any time without risk,
since it never touches anything real; but (2) actually standing up a REAL Kubernetes cluster and
REAL ArgoCD instance, with `allowKubernetesProductionMutation`/`allowArgoCDProductionSync` flipped
from false to a real, authorized true, should wait until the product loop being deployed onto that
substrate has been proven end-to-end in the pilot — otherwise the project risks hardening a
substrate for a product shape that the pilot might still reveal needs to change.

### 哪些現有 test/staging evidence 不能被視為 production evidence?

```text
1. Every "production_executed_true_count = 0" statement across this project's entire history --
   correctly true so far, but it is evidence of "no production action has happened yet," not
   evidence that the system is production-ready. These are different claims.
2. The Stage 60-63A kind-cluster/non-production-ArgoCD dry-run rehearsals -- explicitly and
   repeatedly self-documented as "nonprod ArgoCD != production ArgoCD," "no cluster action, no
   deploy, no sync." Real value as REHEARSAL evidence (the authorization-boundary models are
   sound), zero value as evidence that a production substrate exists or has been validated.
3. The now-decommissioned staging environment (the historical staging host, Step 64-65) -- was a real, more
   production-like environment while it existed (22 containers, real migrations applied), but it
   used `SECRET_PROVIDER=mock-vault`/`ALLOW_VAULT_DEV_MODE_FOR_STAGING=true` and Postgres `trust`
   auth, live integrations disabled/mocked, and it has since been torn down. Nothing about its
   prior existence should be cited today as current evidence of anything -- it no longer exists to
   verify.
4. Vault dev-mode "unsealed and running" status, in any environment -- evidence the service
   responds, not evidence of a real secret-management posture (ephemeral, no HA, no real KMS/auto-
   unseal).
5. The FE.1D-S1 (and every prior FE.1x) test-runtime deployment/validation records -- excellent
   evidence that the FRONTEND POLISH shipped correctly, zero evidence about backend production
   readiness, since none of those stages touched backend/infra/deployment substrate at all.
```

## Definition of production-ready (this project, concretely)

Production-ready means **all** of the following are true simultaneously, not any subset:

```text
1. M1-M5 complete and validated by a real controlled pilot (66H) with a real operator exercising
   the full assign -> execute -> clarify -> deliver -> accept -> notify loop, with no unresolved
   P0/P1 gap discovered during that pilot.
2. A real (non-"kind") Kubernetes cluster and real ArgoCD instance exist, are governed by the
   already-designed (Stage 60-63A) authorization-boundary models re-validated against the real
   substrate, and allowArgoCDProductionSync/allowKubernetesProductionMutation have been
   deliberately, explicitly authorized by the Product Owner for the first time.
3. A real secret store is in place (Vault HA + auto-unseal, or an equivalent cloud KMS-backed
   store) -- ephemeral dev-mode Vault is retired from any environment claiming production status.
4. Postgres authentication is hardened away from `trust`.
5. All four Backup/DR gaps (encryption_no_key, storage_not_off_host, schedule_dry_run_only,
   migration_down_gaps) are closed with real, verified remediation -- not re-stated as "still open"
   for one more stage.
6. The Admin Console SPA deep-link/hard-refresh fallback gap is fixed (a production operator
   bookmarking or refreshing a deep link must not see a raw 404).
7. Team RBAC is a real, server-enforced product feature (not a placeholder), matching the 6-role
   matrix already locked in the 66A.3 blueprint.
8. Every external-send capability (Discord, Slack, Telegram, GitHub, LLM providers) has been
   explicitly, individually authorized for production use by the Product Owner -- no capability
   silently inherits a broader "production is now live" authorization.
9. production_executed_true_count is expected and intended to become nonzero at this point (M7) --
   its value at M6 completion should still be 0, with a documented, explicit Product Owner
   authorization as the trigger for the first real production action at M7, not an implicit
   transition.
```

If even one of these nine is not true, the system should be described as **not yet production-
ready**, regardless of how much frontend polish or how many successful test-runtime deployments have
accumulated.

## Overall alignment result

```text
ALIGNED_WITH_GAPS
```

Rationale: the project's technical state is internally consistent (main, test runtime, and this
analysis all agree; no contradictions found; the canonical milestone order matches the actual
dependency reality). It is not a clean "ALIGNED" because real, material gaps exist that must be
named rather than smoothed over: 66C.4 has been READY_TO_START without being picked up while
cosmetic work continued; the 66D data-model-before-UI discipline has not yet been explicitly
scheduled; and M6's production-substrate requirements (Backup/DR, real secret store, real
Kubernetes/ArgoCD) remain entirely unaddressed beyond non-production rehearsal. None of these gaps
represent a contradiction or a crisis (hence not "NOT_ALIGNED") — they are exactly the kind of
findings this alignment stage exists to surface.

## Statement

Analysis and documentation only. No implementation, merge, deployment, or runtime modification
performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- STEP66ALIGN1_CLAUDE_CODE_VERIFY: PASS -->
