# Alert Receiver Documentation

Stage 40 — AI Agents SWD Platform

## Architecture

The alert receiver is integrated into the orchestrator service (Option B) at `/alerts/*`. No new container is required.

## Endpoints

### GET /alerts/health

Returns receiver status, auth mode, and safety flags.

```json
{
  "status": "ok",
  "receiver_enabled": true,
  "auth_mode": "local_test_unsigned",
  "auth_required": false,
  "external_alert_receiver_authenticated": false,
  "dry_run_escalation_enabled": true,
  "real_escalation_enabled": false,
  "production_executed": false
}
```

### POST /alerts/alertmanager

Accepts Alertmanager webhook payload.

```json
{
  "receiver": "aiagents-receiver",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {"alertname": "HostDown", "severity": "critical", "instance": "host1"},
      "annotations": {"summary": "Host is unreachable"},
      "startsAt": "2026-06-01T00:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "fingerprint": "abc123"
    }
  ],
  "groupLabels": {},
  "commonLabels": {"severity": "critical"},
  "commonAnnotations": {},
  "externalURL": "http://alertmanager:9093",
  "version": "4",
  "groupKey": "{}:{alertname=\"HostDown\"}"
}
```

### POST /alerts/generic

Accepts a simplified generic webhook payload.

```json
{
  "source": "synthetic_test",
  "alert_name": "orchestrator_down",
  "severity": "critical",
  "labels": {"component": "orchestrator"},
  "annotations": {"runbook": "https://..."},
  "fingerprint": "fp123",
  "starts_at": "2026-06-01T00:00:00Z"
}
```

## Authentication

| Mode | Behavior |
|---|---|
| `local_test_unsigned` | No auth check. `ALERT_RECEIVER_SHARED_SECRET` not set. `/operations/safety` shows `external_alert_receiver_authenticated=false`. |
| `shared_secret` | `X-AIAGENTS-ALERT-SIGNATURE` header required. HMAC-SHA256 compared via `hmac.compare_digest`. |

**Production:** shared secret or mTLS required. Currently a known gap.

## Redaction

Before storage, all fields matching the following names are replaced with `[REDACTED]`:
`token`, `secret`, `password`, `authorization`, `api_key`, `webhook_secret`, `access_token`, `refresh_token`, `private_key`

Only the SHA-256 hash of the original payload is stored as `raw_payload_hash`.

## Deduplication

`dedupe_key = SHA-256(source + alert_name + fingerprint + sorted(labels))`

When a matching open/acknowledged/investigating incident exists:
- Alert is linked to existing incident.
- Lifecycle event `incident_linked_to_alert` is recorded.
- No duplicate incident is created.

## Dry-run Escalation

SEV1/SEV2 alerts trigger a dry-run escalation:
- Policy looked up from `incident_escalation_policies` table.
- Lifecycle event `incident_escalated` recorded with `dry_run=true`.
- No real pager/Slack/OpsGenie message is sent.
- `real_escalation_sent=false` always.

## Verification Commands

```bash
# Health check
curl -s http://localhost:8000/alerts/health | python -m json.tool

# Send synthetic Alertmanager alert
curl -s -X POST http://localhost:8000/alerts/alertmanager \
  -H 'Content-Type: application/json' \
  -d '{"receiver":"test","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"TestAlert","severity":"critical"},"annotations":{},"startsAt":"2026-06-01T00:00:00Z","endsAt":"0001-01-01T00:00:00Z","fingerprint":"test-fp"}]}' | python -m json.tool

# Send generic alert
curl -s -X POST http://localhost:8000/alerts/generic \
  -H 'Content-Type: application/json' \
  -d '{"source":"synthetic_test","alert_name":"test_alert","severity":"warning","labels":{},"annotations":{}}' | python -m json.tool

# Verify in operations
curl -s http://localhost:8000/operations/incidents | python -m json.tool
```

## Known Gaps (Production Blockers)

- Shared secret authentication (ALERT_RECEIVER_SHARED_SECRET) not configured on test server.
- mTLS not configured.
- Real pager/Slack/OpsGenie escalation not wired.
- Alertmanager currently routes to null-receiver; adding aiagents-receiver requires operator change.
