# Deferred Work Register — Project Completion Master Plan

> **Consolidated planning document only. No runtime code, no backend, no API, no database, no
> workflow, no new endpoint/route, no merge of any alignment branch, no deployment performed by
> this document.**

Every deferred item below carries an owner milestone, current status, reason deferred, trigger to
activate, and risk if ignored — consolidated from all three partners' risk registers and deferred-
work sections plus this project's own long-standing recorded gaps.

## 1. FE.1D-S2 residual cosmetic work

```text
Owner milestone: absorbed into M1 (TaskList/Workroom labels, relative time), M2 (Delivery/
  placeholder wording), M4 (Notification/Action wording), M6 (safety wording refinements). A
  standalone residual-polish stage only if cosmetic backlog remains after all four absorptions.
Current status: UNAUTHORIZED / NON-CRITICAL. Design + boundary content merged to main as reference
  (Step 66M0-SOT-RECONCILE-M); no implementation authorized.
Reason deferred: does not unblock any milestone; cosmetic polish over surfaces that already work.
Trigger to activate: Product Owner explicitly authorizes it standalone, OR the relevant functional
  milestone (M1/M2/M4/M6) is being built and naturally touches the same file.
Risk if ignored: none to the critical path; a residual-polish backlog if never absorbed anywhere.
```

## 2. TaskWorkroom.tsx body_hash relabel

```text
Owner milestone: M1 (Workroom extraction slice) or M2 (task-delivery technical-details work).
Current status: deferred since Step 66UI.4-FE.1D-TECH-REVIEW; no FE.1D design doc enumerates it.
Reason deferred: narrow scope, not enumerated by any authorized design/boundary document.
Trigger to activate: a Workroom-touching slice in M1 or M2 that would naturally also address it.
Risk if ignored: low — a single raw-hash field remains visible in a technical-details context.
```

## 3. Broad evidence/raw-field relabel (Platform Ops/Audit/Demo-Evidence pages)

```text
Owner milestone: M6 (typed evidence contracts, per Codex's api-contract-dependency-map.md).
Current status: deferred; ~8 pages carry real but unmapped raw column headers.
Reason deferred: no before/after label map exists; needs a dedicated design pass, not a byproduct
  of unrelated work.
Trigger to activate: M6 production-hardening's typed-evidence-contract work (FE-R11, Codex risk
  register).
Risk if ignored: medium for M6/M7 — raw evidence tables stay too technical for real production
  operators (FE-R8).
```

## 4. SPA deep-link fallback

```text
Owner milestone: M6 (must be fixed before M7 rollout).
Current status: known backend/platform gap (docs/frontend/admin-console-spa-deep-link-fallback-
  known-gap.md); accepted as non-blocking through every UI stage to date.
Reason deferred: a backend StaticFiles(html=True) limitation, not frontend-fixable; no stage has
  yet been scoped to fix the backend serving behavior.
Trigger to activate: M6 production-readiness work, before M7 exit.
Risk if ignored: high for M7 — a real production operator bookmarking or refreshing a deep link
  would see a raw 404 (real support-burden risk, not just a test-environment curiosity).
```

## 5. Two-way URL sync

```text
Owner milestone: none currently assigned; excluded from every FE.1x/M1-M4 scope decided so far.
Current status: excluded.
Reason deferred: no milestone currently requires it; adds complexity without a demonstrated need.
Trigger to activate: a future Product Owner decision explicitly requesting it.
Risk if ignored: none identified.
```

## 6. Audit HMAC multi-key rotation

```text
Owner milestone: M6 (production hardening).
Current status: open, carried forward from prior audit-integrity work.
Reason deferred: single-key HMAC is adequate for test-only environments; rotation matters once
  real production audit trails exist.
Trigger to activate: M6 real secret-store migration (naturally co-locates key-rotation work).
Risk if ignored: medium for M6/M7 — a long-lived single audit key is a weaker production posture.
```

## 7. Audit direct-POST integrity gap

```text
Owner milestone: M6 (production hardening).
Current status: open, carried forward from prior audit-integrity work.
Reason deferred: not exercised in test-only traffic patterns; becomes material once external/
  production write paths exist.
Trigger to activate: M4 (external channels) or M6, whichever introduces the first real external
  write path that could exercise this gap.
Risk if ignored: medium — a potential integrity gap on a write path not yet exercised in practice.
```

## 8. DLQ formal Admin Console surface

```text
Owner milestone: M2 (66D — DLQ/Retry P0).
Current status: backend retry-scheduler service running and healthy; no product UI.
Reason deferred: this IS the M2 scope, not a separate deferral — listed here for completeness and
  cross-reference, not because it needs its own trigger beyond M2 starting.
Trigger to activate: Step 66D implementation slices (already in next-executable-stage-sequence.md).
Risk if ignored: high if M2 is skipped or delayed indefinitely — operators cannot recover from
  failures without this surface.
```

## 9. Backup encryption key gap (`encryption_no_key`)

```text
Owner milestone: M6 (must close, one of the nine production-ready conditions).
Current status: open since at least Stage 38, never remediated.
Reason deferred: test-only environment carries no real data at risk; no urgency until M6.
Trigger to activate: M6 entry.
Risk if ignored: high for M6/M7 — a hard blocker for real production readiness; low for M1-M5.
```

## 10. Off-host backup storage (`storage_not_off_host`)

```text
Owner milestone: M6 (must close).
Current status: open since at least Stage 38, never remediated.
Reason deferred: same as #9.
Trigger to activate: M6 entry.
Risk if ignored: high for M6/M7 (single point of failure for backups); low for M1-M5.
```

## 11. Scheduled backup execution (`schedule_dry_run_only`)

```text
Owner milestone: M6 (must close).
Current status: open since at least Stage 38, never remediated; only dry-run schedule exists.
Reason deferred: same as #9.
Trigger to activate: M6 entry.
Risk if ignored: high for M6/M7; low for M1-M5.
```

## 12. Migration down gaps (`migration_down_gaps`)

```text
Owner milestone: M6 (must close).
Current status: open since at least Stage 38, never remediated.
Reason deferred: same as #9.
Trigger to activate: M6 entry.
Risk if ignored: high for M6/M7 (no verified rollback path for schema changes); low for M1-M5.
```

## 13. Production secret backend (real Vault HA/auto-unseal or cloud KMS)

```text
Owner milestone: M6 (must close, one of the nine production-ready conditions).
Current status: ephemeral dev-mode Vault in every environment used so far.
Reason deferred: adequate for test-only use; explicitly named in every relevant stage's safety
  statement, but never remediated to a production-grade posture.
Trigger to activate: M6 entry.
Risk if ignored: high for M6/M7 — root token/unseal key regenerate on every restart; no real
  secret-management posture exists today.
```

## 14. Public repository exposure review

```text
Owner milestone: M6 (production readiness / platform hardening), or earlier if the Product Owner
  decides to make the repository public sooner.
Current status: not yet performed; this project has consistently masked internal IPs/SSH aliases/
  usernames in every committed file to date, but no dedicated "is this repo safe to make public"
  review has been run.
Reason deferred: not urgent while the repository remains private and no production system exists.
Trigger to activate: any Product Owner decision to change repository visibility, or M6 entry.
Risk if ignored: medium — an un-reviewed repo made public could expose something the ongoing
  masking discipline missed (the masking rule is enforced per-stage, not via a single audit pass).
```

## 15. Kubernetes/Helm production substrate

```text
Owner milestone: M6 (must establish, one of the nine production-ready conditions).
Current status: only a non-production "kind" cluster + non-production ArgoCD instance exist
  (Stage 60-63A dry-run rehearsal). No real cluster, ever.
Reason deferred: intentionally sequenced after the M5 pilot proves the product loop, per this
  project's own established caution against hardening a substrate before knowing the pilot didn't
  reveal a design flaw.
Trigger to activate: M5 pilot completion with no unresolved P0/P1 gap.
Risk if ignored: this dry-run work being mistaken for M6 itself is the single most likely
  misreading of this project's state (risk #4 in Claude Code's risk-register.md) — must be
  corrected wherever it appears.
```

## 16. ArgoCD production sync

```text
Owner milestone: M6 (must establish, one of the nine production-ready conditions).
Current status: allowArgoCDProductionSync remains false; no real sync ever performed.
Reason deferred: same as #15.
Trigger to activate: M6, after the real cluster (#15) is established and re-validated.
Risk if ignored: same as #15 — must not be confused with completed M6 work.
```

## 17. SLO/capacity/on-call readiness

```text
Owner milestone: M6/M7 (production readiness and rollout).
Current status: not yet defined; no SLO/capacity model or on-call rotation exists.
Reason deferred: meaningless before a real production substrate and real user load exist.
Trigger to activate: M6 entry (definition) and M7 entry (activation).
Risk if ignored: high for M7 — production rollout without SLO/capacity/on-call readiness risks an
  unmanaged incident with no defined response process.
```

## Statement

Consolidated planning document only. No runtime code, no backend, no API, no database, no workflow,
no new endpoint/route, no merge of any alignment branch, no deployment performed by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
