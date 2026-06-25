# Agent-Specific Threat Model (Step 54.4)

Source: [`infra/security/agent-threat-model.yaml`](../../infra/security/agent-threat-model.yaml)

Agentic-AI threats (`AG-001`..`AG-015`): workspace modification, code generation,
deployment recommendation, verification, delivery package, approval misjudgement,
wrong-context reference, prompt injection, tool misuse, unauthorized production
action, human-approval bypass, audit omission, secret exfiltration, and the future
GitHub-write / ArgoCD-sync risks.

Existing mitigations are enumerated (human approval for production, the
`production_executed` flag, HARD_SAFETY_ACTIONS, operator allowlist, audit trail,
identity boundary, secret redaction, runtime read-only, no GitHub write, no
deploy/sync, no external upload). Prompt injection and agent goal drift remain
**partially mitigated** and are production blockers. `productionReady: false`.

## Verify
`python scripts/verify_agent_threat_model.py` → `AGENT_THREAT_MODEL_VERIFY: PASS`.
API: `GET /operations/security/threat-model/agent`.
