# Project Process Memory

Before any implementation, architecture review, validation, blocker classification,
governance change, or roadmap-affecting work, read
`docs/governance/AI_AGENTS_PROJECT_EXECUTION_STANDARD.md`. Treat it as binding
project process memory.

- A failing test is not automatically a blocker: classify the protected risk first.
- Only concrete P0/P1 risks block by default; P2/P3 findings default to defer,
  informational, pre-production, or historical-only handling.
- Real Git and runtime lifecycle evidence outranks synthetic fixtures.
- Return architecture or design-premise findings to Design Review; do not add a
  remediation layer inside validation.
- Do not change product or runtime behavior solely to satisfy stale historical or
  meta-governance guards.
- On a contradiction with this standard, emit `GOVERNANCE_DRIFT_ALERT` using the
  exact format defined in the standard before proceeding.
