# Step 66C.4-BE1-R1 Payload Safety Remediation Record (M-1)

> **Remediation record. No live producer. No deployment. No merge. No secret handled.**

## The defect

`assert_safe_outbox_payload` iterated only the TOP-LEVEL keys of the payload and compared each
against an exact-match deny list. The independent security review probed it directly:

```text
{'meta': {'answer': '<raw clarification body>'}}   -> ACCEPTED
{'items': [{'token': '<secret>'}]}                 -> ACCEPTED
{'answer_body': 'raw body text'}                   -> ACCEPTED
{'question_text': 'raw question'}                  -> ACCEPTED
{'ANSWER': 'x'}                                    -> rejected (case folding worked)
```

Nesting bypassed it entirely, and exact matching let near-miss names through. The canonical
contract requires the payload to be "minimal, safe (no raw question/answer body; hash/length refs
only)"; the deny list enforced only a narrow subset of that.

## The correction

The deny list is REPLACED by a positive, per-event-type key allowlist plus a scalar-only value rule.
A deny list must anticipate every unsafe name; an allowlist only has to enumerate the safe ones, and
the canonical event payload contract already does.

```text
ALLOWED_PAYLOAD_KEYS_BY_EVENT_TYPE  -- event_type -> the exact permitted key set
  clarification.reminder_due        : event_id, occurred_at, reason, reminder_at
  clarification.reminder_recorded   : + reminder_sent_at
  clarification.expired             : event_id, occurred_at, reason, due_at, expired_at
  clarification.resume_eligible     : event_id, occurred_at, reason, resume_eligible_at
  clarification.resume_requested    : + resume_requested_at, resume_requested_by
  clarification.resume_authorized   : event_id, occurred_at, reason, resume_authorized_at

Event naming now follows the canonical api-and-event-contract.md 11.2 dotted convention
(clarification.reminder_recorded), replacing BE1's inconsistent underscore names.
Dispatch / resume-dispatched / workflow-resumed events remain OUT of the allowlist -- they are BE3
scope and this stage must not widen it.

Rejected by default:
  unknown event_type, unknown key, nested dict, list, non-scalar value, float,
  over-long string value (>500 chars), oversized payload (>2000 bytes),
  any key owned by a dedicated outbox COLUMN (clarification_id, task_id, event_type,
  idempotency_key, status, attempts) -- no duplicate storage.

Allowed value types: str (bounded), int, bool, None. Nothing else.
```

## Bypass probes (all now REJECTED)

```text
{"meta": {"answer": "raw"}}            -> rejected (unknown key + nested)
{"items": [{"token": "secret"}]}       -> rejected (unknown key + list)
{"answer_body": "raw"}                 -> rejected (unknown key)
{"question_text": "raw"}               -> rejected (unknown key)
{"TOKEN": "secret"}                    -> rejected (unknown key, case-folded)
{"unknown_key": "value"}               -> rejected (unknown key)
{"answer": "raw"}                      -> rejected (unknown key)
{"reason": {"nested": "dict"}}         -> rejected (non-scalar value)
{"reason": ["list"]}                   -> rejected (non-scalar value)
{"reason": 1.5}                        -> rejected (non-scalar value)
{"clarification_id": "<uuid>"}         -> rejected (column-owned key)
{"task_id": "<uuid>"}                  -> rejected (column-owned key)
oversized value / oversized payload    -> rejected
unknown event_type                     -> rejected
```

Error messages name the offending KEY only. A dedicated test asserts a secret VALUE never appears
in the raised error text.

## Residual, recorded

```text
The payload size cap and the event-type allowlist are enforced in the repository helper.
last_error is now additionally bounded by a DB CHECK constraint, because it is written on every
failure path. A DB-level payload-size or event-type CHECK was NOT added: it is weak against the
only threat it would address (a future producer bypassing the helper with raw SQL can equally
construct a payload that satisfies a size CHECK), and adding schema beyond what the findings
require is the self-expansion this stage must avoid. Recorded as deferred L-1.
idempotency_key format validation remains unimplemented (independent review L-2). Keys are
server-derived and deterministic today, and there is no producer. Recorded as deferred L-2.
Both are tracked in be1-deferred-low-findings.md.
```

## Statement

Remediation record only. No live producer. No relay. No scheduler. No external notification. No
deployment. No merge. No secret handled or stored.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
