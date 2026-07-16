# Overview Microcopy Guide — DESIGN-66UI.4-FE.1C

> Owner: Claude Design. Overview-specific strings, consistent with the merged Phase 1
> `product-microcopy-guide.md`. Product language, active voice, reassurance-first. UI strings in
> English (matching the app).

## Page header

```text
Title:    Overview
Subtitle: See what your AI team needs from you and where work stands.
```

(Replaces "Executive Overview" — less corporate-report, more product.)

## Section headers

```text
Needs your attention
AI team activity
Current work
System posture
Platform & delivery metrics      (demoted section)
Future capabilities
```

## Needs-your-attention tiles

| Tile | Copy (count > 0) | Empty / placeholder |
| --- | --- | --- |
| Decisions waiting | "N — agents waiting on your answer" | "You're all caught up." |
| Blocked tasks | "N — waiting on an input" | "Nothing blocked." |
| Deliveries to review | (placeholder) | "Not yet available. Requires Step 66D." |
| Approvals queue | (placeholder) | "Not yet available. Requires Step 66D." |

## AI team activity

```text
Header: AI team activity
Row:    "<Agent name> — <status> · <relative time>"   e.g. "Requirement Agent — completed · 2h ago"
Empty:  "No recent agent runs."
```

Status words are product-readable (completed / running / needs input / failed), mapped from the
existing agent-execution data — not raw backend enums surfaced verbatim.

## Current work

```text
Header: Current work
Row:    "<Task title> — <product status> · <relative time>"
        e.g. "Build SaaS User Management Module — Clarification needed · 2h ago"
Empty:  "No tasks yet. Assign your first piece of work to the AI team."
```

Product status mapping (examples): `clarification_needed` → "Clarification needed";
`blocked` → "Blocked"; `development` → "In development"; `delivery_ready` → "Ready for delivery".
Exact timestamps available on hover; the row shows relative time.

## System posture

```text
Safe state:    "🛡 Safe — no automated or production actions will run."
Link:          "View Safety →"
```

Reuses the FE.1B posture summary; does not restate the individual safety fields (FE.1B owns that).

## Future capabilities

```text
Delivery Review:  "Not yet available. Requires Step 66D. No workflow action available from this screen."
Reminder/Expiry:  "Not yet available. Requires Step 66C.4. No workflow action available from this screen."
Notifications:    "Future. No workflow action available from this screen."
Pipeline view:    "Future (read-only only). No workflow action available from this screen."
```

## Tone rules (carried from Phase 1)

- Name things by what a person does; no raw `snake_case` field names in primary copy.
- Zero/empty attention = good news, phrased calmly ("You're all caught up"), never a red alarm.
- Reassurance-first for safety; consequence-explicit for links.
- Errors: "This information isn't available for your role right now." — readable, never a raw code.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
