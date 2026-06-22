# Session Concurrency Policy (Step 52.3)

Source: [session-concurrency-policy.yaml](../../infra/identity/session-concurrency-policy.yaml).

* **Current behaviour:** `recorded_not_enforced`. Multiple sessions per identity
  are allowed; sessions are counted by `identity_id` + active status (the
  `admin_console_sessions` table already indexes `(identity_id, status)`).
* **Production policy:** required; `maxConcurrentSessions` not yet set;
  enforcement **deferred to production auth**.
* **Suspicious patterns** to detect in future: excessive active sessions,
  impossible travel, role escalation during a session.

No automatic session termination is performed in this step.
