# Session Hardening Model (Step 52.3)

Status: **hardened test baseline; not production-ready.** Source:
[session-hardening-catalog.yaml](../../infra/identity/session-hardening-catalog.yaml).

## Current posture

* Cookie: HttpOnly, SameSite=Strict, Secure required in production (configurable
  in dev/test).
* Expiry: 30-minute absolute timeout. Idle timeout is **required before
  production** (not yet configured).
* Persistence: server-side session; raw token **never** persisted; only
  `sha256(token)` (`session_hash`) is stored.
* Cleanup: a non-destructive cleanup utility exists
  ([session_cleanup.py](../../shared/sdk/identity/session_cleanup.py)) — see
  below.
* Concurrency: recorded, not enforced ([session-concurrency-policy.md](session-concurrency-policy.md)).
* Forced logout: server-side revoke supported; user-level / role-change forced
  logout modelled, not production-ready ([forced-logout-model.md](forced-logout-model.md)).
* Key rotation: model only ([session-key-rotation-model.md](session-key-rotation-model.md)).

## Cleanup utility

`plan_cleanup(sessions, now)` is pure: it preserves active-and-valid sessions,
slates only active-past-expiry sessions to `expired`, counts `expired`/`revoked`
without touching them, and references only `session_hash`/`status`/`expires_at`
(no raw token). `run_cleanup(...)` applies it via asyncpg with a `dry_run`
default and **never deletes** a row. The `admin_console_sessions` schema (Step 50,
migration 023) already supports this — no migration was added.

## Production blockers

Idle timeout, concurrency enforcement, production secret store for the session
signing key, and a finalized admin/break-glass identity are all still required.
The current runtime key file / ephemeral secret is **not** production-ready and
is never committed.
