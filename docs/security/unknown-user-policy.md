# Unknown User Policy (Step 52.3)

Source: [unknown-user-policy.yaml](../../infra/identity/unknown-user-policy.yaml).

Any unidentifiable, unverified, or unmapped user is **denied**:

| Condition | Result |
|---|---|
| missing subject | deny |
| missing email | deny |
| email not verified | deny |
| missing groups | deny |
| no group match | deny |

No default role, no auto-viewer, no self-registration, no just-in-time
provisioning, no platform_admin fallback, no token-role-claim authority. The
role mapping engine enforces every one of these deny paths
([role-mapping-policy.md](role-mapping-policy.md)).

Audit: a denied attempt is recorded **without** the raw token, raw email, or raw
groups. Production status: not ready until a real role mapping is configured.
