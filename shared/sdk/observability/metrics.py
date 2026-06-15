from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Workflow-level metrics (orchestrator)
WORKFLOW_TOTAL = Counter(
    "workflow_total",
    "Workflows dispatched, labelled by terminal status when known",
    ["status"],
)
WORKFLOW_COMPLETED_TOTAL = Counter(
    "workflow_completed_total",
    "Workflows that reached stage=completed",
)
WORKFLOW_FAILED_TOTAL = Counter(
    "workflow_failed_total",
    "Workflows that ended in a non-success terminal stage",
    ["reason"],  # canceled | aborted | rejected | failed
)
WORKFLOW_DURATION_SECONDS = Histogram(
    "workflow_duration_seconds",
    "End-to-end workflow duration (dispatch -> completed)",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)

# Agent-level metrics
AGENT_EXECUTION_TOTAL = Counter(
    "agent_execution_total",
    "Agent execution invocations",
    ["agent", "status"],  # status = completed | failed
)
AGENT_EXECUTION_FAILURES_TOTAL = Counter(
    "agent_execution_failures_total",
    "Agent execution failures",
    ["agent"],
)
AGENT_LATENCY_SECONDS = Histogram(
    "agent_latency_seconds",
    "Per-agent processing latency",
    ["agent"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Retry / dead-letter / scheduler metrics
DEADLETTER_TOTAL = Counter(
    "deadletter_total",
    "Dead-letter publications, labelled by the original stream",
    ["original_stream"],
)
RETRY_TOTAL = Counter(
    "retry_total",
    "Retry events, labelled by kind",
    ["kind"],  # requeued | terminal_failure | manual_replay
)

# Notification metrics
NOTIFICATION_TOTAL = Counter(
    "notification_total",
    "Notifications published, labelled by event_type",
    ["event_type"],
)

# GitHub automation metrics
GITHUB_ISSUE_CREATED_TOTAL = Counter(
    "github_issue_created_total",
    "GitHub issues created (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_BRANCH_CREATED_TOTAL = Counter(
    "github_branch_created_total",
    "GitHub branches created (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_PR_CREATED_TOTAL = Counter(
    "github_pr_created_total",
    "GitHub pull requests created (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_CHECKS_READ_TOTAL = Counter(
    "github_checks_read_total",
    "GitHub check-runs read (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_AUTOMATION_FAILURES_TOTAL = Counter(
    "github_automation_failures_total",
    "Failures in the github-automation pipeline (labelled by operation)",
    ["operation"],
)
GITHUB_PIPELINE_INTEGRATION_TOTAL = Counter(
    "github_pipeline_integration_total",
    "Agent-pipeline -> github-automation integrations (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_PIPELINE_INTEGRATION_FAILURES_TOTAL = Counter(
    "github_pipeline_integration_failures_total",
    "Agent-pipeline -> github-automation integration failures",
    ["reason"],  # http_error | safe_failure | disabled (informational)
)

# Controlled real GitHub validation metrics (Stage 23)
GITHUB_REAL_TEST_ATTEMPTS_TOTAL = Counter(
    "github_real_test_attempts_total",
    "Controlled real GitHub test attempts (labelled by repo+result)",
    ["repo", "result"],  # result: attempted (guard passed, run started)
)
GITHUB_REAL_TEST_SUCCESS_TOTAL = Counter(
    "github_real_test_success_total",
    "Controlled real GitHub tests that completed the full PR flow",
    ["repo", "result"],  # result: completed
)
GITHUB_REAL_TEST_BLOCKED_TOTAL = Counter(
    "github_real_test_blocked_total",
    "Controlled real GitHub tests refused by the safety guard",
    ["repo", "reason"],
)
GITHUB_REAL_TEST_FAILURES_TOTAL = Counter(
    "github_real_test_failures_total",
    "Controlled real GitHub tests that started but failed mid-flow",
    ["repo", "reason"],
)
GITHUB_REAL_TEST_DURATION_SECONDS = Histogram(
    "github_real_test_duration_seconds",
    "Controlled real GitHub test wall-clock duration (full PR flow)",
    ["repo", "result"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

# Audit-worker metrics (Stage 19 stream.audit -> audit_logs persistence)
AUDIT_WORKER_PROCESSED_TOTAL = Counter(
    "audit_worker_processed_total",
    "Audit events persisted into audit_logs by audit-worker",
    ["decision_type"],
)
AUDIT_WORKER_FAILURES_TOTAL = Counter(
    "audit_worker_failures_total",
    "Audit events whose persistence failed (labelled by reason)",
    ["reason"],  # normalize_error | db_error | deadletter_error
)
AUDIT_WORKER_DEADLETTERED_TOTAL = Counter(
    "audit_worker_deadlettered_total",
    "Audit events routed to stream.deadletter by audit-worker",
)
AUDIT_WORKER_SKIPPED_TOTAL = Counter(
    "audit_worker_skipped_total",
    "Audit events skipped without persisting (labelled by reason)",
    ["reason"],  # audit_recorded_echo | duplicate | empty
)
AUDIT_WORKER_PROCESSING_SECONDS = Histogram(
    "audit_worker_processing_seconds",
    "End-to-end audit-worker processing time per event",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# Operations Control API metrics (Stage 20 — unified read-only operator view)
OPERATIONS_REQUESTS_TOTAL = Counter(
    "operations_requests_total",
    "Operations Control API requests (labelled by endpoint and result)",
    ["endpoint", "result"],  # result = ok | error | not_found
)
OPERATIONS_REQUEST_FAILURES_TOTAL = Counter(
    "operations_request_failures_total",
    "Operations Control API failures (labelled by endpoint and reason)",
    ["endpoint", "reason"],  # reason = store_error | not_found | bad_request
)
OPERATIONS_REQUEST_DURATION_SECONDS = Histogram(
    "operations_request_duration_seconds",
    "Operations Control API per-endpoint duration",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# Discord Gateway sandbox metrics (Stage 21)
DISCORD_MESSAGES_RECEIVED_TOTAL = Counter(
    "discord_messages_received_total",
    "Discord-sandbox messages received by the gateway",
    ["command_type", "sandbox"],
)
DISCORD_TASKS_DISPATCHED_TOTAL = Counter(
    "discord_tasks_dispatched_total",
    "Discord-sandbox messages that produced a workflow dispatch",
    ["command_type", "result", "sandbox"],
)
DISCORD_INTAKE_FAILURES_TOTAL = Counter(
    "discord_intake_failures_total",
    "Discord-sandbox intake failures (labelled by reason)",
    ["reason"],  # parse_error | gateway_error | dispatch_error
)
DISCORD_NOTIFICATIONS_PUBLISHED_TOTAL = Counter(
    "discord_notifications_published_total",
    "Discord-sandbox notifications published to stream.notifications",
    ["event_type", "sandbox"],
)
DISCORD_REQUEST_DURATION_SECONDS = Histogram(
    "discord_request_duration_seconds",
    "Discord-gateway per-endpoint duration",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# Notification-worker metrics (Stage 22 — controlled Discord delivery)
NOTIFICATION_WORKER_PROCESSED_TOTAL = Counter(
    "notification_worker_processed_total",
    "Notification events consumed from stream.notifications",
    ["event_type"],
)
NOTIFICATION_WORKER_DELIVERED_TOTAL = Counter(
    "notification_worker_delivered_total",
    "Notifications dispatched as real Discord deliveries",
    ["event_type", "channel"],
)
NOTIFICATION_WORKER_SIMULATED_TOTAL = Counter(
    "notification_worker_simulated_total",
    "Notifications recorded as sandbox simulations (no external API call)",
    ["event_type", "channel"],
)
NOTIFICATION_WORKER_FAILURES_TOTAL = Counter(
    "notification_worker_failures_total",
    "Notification deliveries that failed (labelled by reason)",
    ["reason"],  # render_error | store_error | discord_error | deadletter_error
)
NOTIFICATION_WORKER_SKIPPED_TOTAL = Counter(
    "notification_worker_skipped_total",
    "Notifications skipped without delivery (labelled by reason)",
    ["reason"],  # duplicate | empty | sandbox_self_test
)
NOTIFICATION_WORKER_PROCESSING_SECONDS = Histogram(
    "notification_worker_processing_seconds",
    "End-to-end notification-worker processing time per event",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# Stage 33 — real Discord delivery policy decisions.
REAL_DISCORD_DELIVERY_ALLOWED_TOTAL = Counter(
    "real_discord_delivery_allowed_total",
    "Stream events promoted to real Discord delivery (per event_type)",
    ["event_type"],
)
REAL_DISCORD_DELIVERY_BLOCKED_TOTAL = Counter(
    "real_discord_delivery_blocked_total",
    "Stream events blocked from real Discord delivery (per event_type + reason)",
    ["event_type", "reason"],
)
REAL_DISCORD_DELIVERY_SKIPPED_TOTAL = Counter(
    "real_discord_delivery_skipped_total",
    "Stream events skipped by the real-delivery policy (per event_type + reason)",
    ["event_type", "reason"],
)
REAL_DISCORD_DELIVERY_POLICY_DECISIONS_TOTAL = Counter(
    "real_discord_delivery_policy_decisions_total",
    "Every real-delivery policy decision (per event_type + decision + reason)",
    ["event_type", "decision", "reason"],
)

# Stage 34 — tamper-evident audit chain metrics.
AUDIT_INTEGRITY_RECORDS_TOTAL = Counter(
    "audit_integrity_records_total",
    "audit_integrity_records rows written (per chain_version + status)",
    ["chain_version", "status"],
)
AUDIT_INTEGRITY_MISSING_TOTAL = Counter(
    "audit_integrity_missing_total",
    "audit_logs rows observed lacking an integrity record",
    ["reason"],
)
AUDIT_INTEGRITY_VERIFICATION_RUNS_TOTAL = Counter(
    "audit_integrity_verification_runs_total",
    "Verification-chain runs executed (per chain_version + status)",
    ["chain_version", "status"],
)
AUDIT_INTEGRITY_VERIFICATION_FAILED_TOTAL = Counter(
    "audit_integrity_verification_failed_total",
    "Verification-chain runs that ended failed/error (per reason)",
    ["reason"],
)
AUDIT_INTEGRITY_DEGRADED_TOTAL = Counter(
    "audit_integrity_degraded_total",
    "Audit-integrity writes that failed -- worker degraded but audit row persisted",
    ["reason"],
)
AUDIT_TAMPER_DETECTED_TOTAL = Counter(
    "audit_tamper_detected_total",
    "Tamper events detected by the verifier",
    ["reason"],
)

# Stage 39 -- audit integrity HMAC keyring + direct POST integrity closure.
AUDIT_HMAC_KEYRING_LOAD_TOTAL = Counter(
    "audit_hmac_keyring_load_total",
    "Keyring load attempts (per mode + source)",
    ["mode", "source"],
)
AUDIT_HMAC_KEYRING_INVALID_TOTAL = Counter(
    "audit_hmac_keyring_invalid_total",
    "Keyring loads that ended in mode=invalid (per reason)",
    ["reason"],
)
AUDIT_SIGNATURE_VERIFIED_TOTAL = Counter(
    "audit_signature_verified_total",
    "HMAC signature verifications that succeeded (per signing_key_id + mode)",
    ["mode", "signing_key_id"],
)
AUDIT_SIGNATURE_FAILED_TOTAL = Counter(
    "audit_signature_failed_total",
    "HMAC signature verifications that failed (per reason + mode)",
    ["mode", "reason"],
)
AUDIT_SIGNATURE_KEY_MISSING_TOTAL = Counter(
    "audit_signature_key_missing_total",
    "Signed rows whose signing_key_id is no longer in the keyring (per mode)",
    ["mode"],
)
AUDIT_DIRECT_POST_INTEGRITY_CREATED_TOTAL = Counter(
    "audit_direct_post_integrity_created_total",
    "Integrity records created via the audit-service direct POST path",
    ["status"],
)
AUDIT_DIRECT_POST_INTEGRITY_FAILURES_TOTAL = Counter(
    "audit_direct_post_integrity_failures_total",
    "Direct POST integrity writes that failed and forced a transaction rollback",
    ["reason"],
)
AUDIT_INTEGRITY_SEQUENCE_LOCK_WAIT_SECONDS = Histogram(
    "audit_integrity_sequence_lock_wait_seconds",
    "Seconds spent waiting for the audit_integrity advisory lock",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5),
)
AUDIT_INTEGRITY_CONCURRENCY_RETRIES_TOTAL = Counter(
    "audit_integrity_concurrency_retries_total",
    "Sequence-conflict retries triggered while inserting an integrity record",
    ["reason"],
)

# Stage 35 -- LLM cost governance + real-LLM plan-only pilot.
LLM_BUDGET_PREFLIGHT_TOTAL = Counter(
    "llm_budget_preflight_total",
    "Budget preflight evaluations executed (per provider + decision + reason)",
    ["provider", "decision", "reason"],
)
LLM_BUDGET_ALLOWED_TOTAL = Counter(
    "llm_budget_allowed_total",
    "Budget preflights that returned decision=allowed",
    ["provider", "model"],
)
LLM_BUDGET_BLOCKED_TOTAL = Counter(
    "llm_budget_blocked_total",
    "Budget preflights that returned decision=blocked (per reason)",
    ["provider", "reason"],
)
LLM_REAL_PLAN_CALLS_TOTAL = Counter(
    "llm_real_plan_calls_total",
    "Real-LLM plan-only calls attempted (per provider + model + result)",
    ["provider", "model", "result"],
)
LLM_REAL_PLAN_BLOCKED_TOTAL = Counter(
    "llm_real_plan_blocked_total",
    "Real-LLM plan-only calls blocked by guard or budget (per reason)",
    ["provider", "reason"],
)
LLM_COST_USD_TOTAL = Counter(
    "llm_cost_usd_total",
    "Cumulative LLM cost in USD (rounded to 6 decimals)",
    ["provider", "model"],
)
LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Cumulative LLM tokens consumed (per provider + model + kind)",
    ["provider", "model", "kind"],  # kind: prompt | completion | total
)


# Stage 27 — flexible task execution loop metrics.
TASK_WORK_ITEMS_TOTAL = Counter(
    "task_work_items_total",
    "Task work items written (one row per upsert)",
    ["execution_mode", "status"],
)
TASK_EXECUTION_MODE_TOTAL = Counter(
    "task_execution_mode_total",
    "Classifier decisions, labelled by chosen execution mode + request_type",
    ["execution_mode", "request_type"],
)
CLARIFICATION_REQUESTS_TOTAL = Counter(
    "clarification_requests_total",
    "Clarification requests by lifecycle (requested | answered)",
    ["status"],
)
TASK_READY_FOR_DEVELOPMENT_TOTAL = Counter(
    "task_ready_for_development_total",
    "Work items that reached status=ready_for_development",
    ["execution_mode"],
)
TASK_BLOCKED_TOTAL = Counter(
    "task_blocked_total",
    "Work items that were marked blocked",
    ["reason"],
)
AGENT_DISCUSSIONS_TOTAL = Counter(
    "agent_discussions_total",
    "Agent discussion rows appended",
    ["agent", "message_type"],
)


# Stage 28 — controlled code generation workspace metrics.
CODE_WORKSPACES_TOTAL = Counter(
    "code_workspaces_total",
    "Code workspaces created (one row per upsert)",
    ["execution_mode", "generator_mode", "status"],
)
CODE_GENERATION_ATTEMPTS_TOTAL = Counter(
    "code_generation_attempts_total",
    "Deterministic code generation attempts",
    ["execution_mode", "generator_mode"],
)
CODE_GENERATION_SUCCESS_TOTAL = Counter(
    "code_generation_success_total",
    "Code generation runs that produced at least one valid artifact",
    ["execution_mode", "generator_mode", "risk_level"],
)
CODE_GENERATION_BLOCKED_TOTAL = Counter(
    "code_generation_blocked_total",
    "Code generation runs blocked by policy / allowlist / classifier",
    ["reason"],
)
CODE_VALIDATION_FAILURES_TOTAL = Counter(
    "code_validation_failures_total",
    "Per-file validation failures (labelled by failure kind)",
    ["check"],  # check = allowlist | secret_content | py_compile | diff_empty | file_missing
)
PR_DRAFT_ARTIFACTS_TOTAL = Counter(
    "pr_draft_artifacts_total",
    "PR draft artifacts created",
    ["execution_mode", "status", "risk_level"],
)


# Stage 29 — QA-guided validation + deterministic auto-fix loop.
QA_VALIDATION_RUNS_TOTAL = Counter(
    "qa_validation_runs_total",
    "QA validation runs started",
    ["status"],
)
QA_VALIDATION_PASSED_TOTAL = Counter(
    "qa_validation_passed_total",
    "QA validation runs that ended with final_result=pass",
)
QA_VALIDATION_FAILED_TOTAL = Counter(
    "qa_validation_failed_total",
    "QA validation runs that ended with final_result=fail",
    ["reason"],  # auto_fix_max_attempts | blocked | validation_error
)
QA_FINDINGS_TOTAL = Counter(
    "qa_findings_total",
    "QA findings recorded",
    ["severity", "category", "auto_fixable"],
)
QA_AUTO_FIX_REQUESTS_TOTAL = Counter(
    "qa_auto_fix_requests_total",
    "Auto-fix requests filed by the qa-agent",
    ["status"],  # requested | completed | failed | max_attempts_exceeded
)
QA_BLOCKED_FOR_HUMAN_REVIEW_TOTAL = Counter(
    "qa_blocked_for_human_review_total",
    "QA runs that escalated to human review",
    ["reason"],
)
QA_AUTO_FIX_ATTEMPTS_TOTAL = Counter(
    "qa_auto_fix_attempts_total",
    "Auto-fix attempts executed by the development-agent",
    ["result"],  # completed | failed | max_attempts_exceeded
)


# Stage 30 — LLM-assisted development planning guardrails.
LLM_INTERACTIONS_TOTAL = Counter(
    "llm_interactions_total",
    "LLM interactions recorded (one row per call)",
    ["provider", "model", "interaction_type", "status"],
)
LLM_PROPOSALS_TOTAL = Counter(
    "llm_proposals_total",
    "LLM proposal artifacts created",
    ["provider", "proposal_type", "status"],
)
LLM_POLICY_BLOCKS_TOTAL = Counter(
    "llm_policy_blocks_total",
    "LLM proposals blocked by the safety policy",
    ["rule"],  # path_blocked | change_type_blocked | secret_like_content | …
)
LLM_REAL_CALLS_TOTAL = Counter(
    "llm_real_calls_total",
    "Real (network) LLM calls attempted",
    ["provider", "result"],  # result = attempted | skipped
)
LLM_REAL_CALLS_BLOCKED_TOTAL = Counter(
    "llm_real_calls_blocked_total",
    "Real LLM calls blocked by the safety guard",
    ["provider", "reason"],
)
LLM_TOKEN_USAGE_TOTAL = Counter(
    "llm_token_usage_total",
    "LLM token usage (mock provider always increments by 0)",
    ["provider", "model"],
)
LLM_ESTIMATED_COST_TOTAL = Counter(
    "llm_estimated_cost_total",
    "LLM estimated cost (mock provider always increments by 0)",
    ["provider", "model"],
)


# Stage 31 -- flexible human approval policy + LLM proposal promotion.
APPROVAL_POLICIES_TOTAL = Counter(
    "approval_policies_total",
    "Human approval policies created (one row per upsert)",
    ["approval_mode", "scope_type"],
)
APPROVAL_POLICY_ACTIVE_TOTAL = Counter(
    "approval_policy_active_total",
    "Approval policies activated",
    ["approval_mode", "scope_type"],
)
APPROVAL_POLICY_REVOKED_TOTAL = Counter(
    "approval_policy_revoked_total",
    "Approval policies revoked",
    ["approval_mode", "scope_type"],
)
APPROVAL_POLICY_DECISIONS_TOTAL = Counter(
    "approval_policy_decisions_total",
    "Human approval decisions recorded",
    ["approval_mode", "action_type", "decision"],
)
APPROVAL_POLICY_ACTION_ALLOWED_TOTAL = Counter(
    "approval_policy_action_allowed_total",
    "Actions authorised by an active approval policy",
    ["approval_mode", "action_type"],
)
APPROVAL_POLICY_ACTION_BLOCKED_TOTAL = Counter(
    "approval_policy_action_blocked_total",
    "Actions blocked by policy or hard safety rails",
    ["reason", "action_type"],
)
DELEGATED_ACTIONS_USED_TOTAL = Counter(
    "delegated_actions_used_total",
    "Per-policy delegated-action consumption (max_actions guard)",
    ["scope_type"],
)
LLM_PROMOTIONS_TOTAL = Counter(
    "llm_promotions_total",
    "LLM proposal promotion attempts (status label)",
    ["promotion_mode", "status"],
)

# Stage 32 -- real Discord / GitHub sandbox pilot metrics.
REAL_DISCORD_TESTS_TOTAL = Counter(
    "real_discord_tests_total",
    "Real Discord test messages dispatched (result label)",
    ["result"],  # sent | blocked | error
)
REAL_DISCORD_TASKS_TOTAL = Counter(
    "real_discord_tasks_total",
    "Real Discord controlled-test task intakes",
    ["result"],  # received | blocked | error
)
REAL_DISCORD_GUARD_BLOCKS_TOTAL = Counter(
    "real_discord_guard_blocks_total",
    "Real Discord guard refusals (reason label)",
    ["reason"],
)
REAL_GITHUB_SANDBOX_PRS_TOTAL = Counter(
    "real_github_sandbox_prs_total",
    "Real GitHub sandbox PRs (result label)",
    ["result"],  # created | blocked | error
)
REAL_GITHUB_GUARD_BLOCKS_TOTAL = Counter(
    "real_github_guard_blocks_total",
    "Real GitHub sandbox guard refusals (reason label)",
    ["reason"],
)
REAL_INTEGRATION_FAILURES_TOTAL = Counter(
    "real_integration_failures_total",
    "Failures while talking to a real Discord / GitHub endpoint",
    ["provider", "reason"],
)


# Stage 36 -- backup / restore / DR drill metrics.
BACKUP_CREATED_TOTAL = Counter(
    "backup_created_total",
    "Backup artifacts produced (per environment + storage_mode + encrypted)",
    ["environment", "storage_mode", "encrypted"],
)
BACKUP_ENCRYPTED_TOTAL = Counter(
    "backup_encrypted_total",
    "Backup artifacts that completed the encryption step",
    ["mode"],
)
BACKUP_UPLOAD_SKIPPED_TOTAL = Counter(
    "backup_upload_skipped_total",
    "Off-host backup uploads that were SKIPPED (per reason)",
    ["mode", "reason"],
)
BACKUP_UPLOAD_SUCCESS_TOTAL = Counter(
    "backup_upload_success_total",
    "Off-host backup uploads that succeeded",
    ["mode"],
)
RESTORE_DRILL_RUNS_TOTAL = Counter(
    "restore_drill_runs_total",
    "Restore drills attempted",
    ["status"],  # passed | failed
)
RESTORE_DRILL_FAILED_TOTAL = Counter(
    "restore_drill_failed_total",
    "Restore drills that ended status=failed (per reason)",
    ["reason"],
)
BACKUP_DURATION_SECONDS = Histogram(
    "backup_duration_seconds",
    "End-to-end backup_postgres duration",
    buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600),
)
RESTORE_DURATION_SECONDS = Histogram(
    "restore_duration_seconds",
    "End-to-end pg_restore duration (isolated DB)",
    buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600),
)
BACKUP_ARTIFACT_SIZE_BYTES = Histogram(
    "backup_artifact_size_bytes",
    "Encrypted backup artifact size in bytes",
    buckets=(1024, 10_240, 102_400, 1_048_576, 10_485_760, 104_857_600, 1_073_741_824),
)
BACKUP_RTO_SECONDS = Histogram(
    "backup_rto_seconds",
    "Measured RTO (total drill duration) per restore drill",
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
)
BACKUP_RPO_SECONDS = Histogram(
    "backup_rpo_seconds",
    "Estimated RPO (latest backup age) per measurement",
    buckets=(60, 300, 900, 1800, 3600, 7200, 21_600, 86_400, 604_800),
)


# Stage 38 -- LLM Model Routing & Agent Model Policy metrics.
LLM_MODEL_ROUTING_REQUESTS_TOTAL = Counter(
    "llm_model_routing_requests_total",
    "ModelRouter requests received (per agent + capability)",
    ["agent_name", "capability"],
)
LLM_MODEL_ROUTING_SELECTED_TOTAL = Counter(
    "llm_model_routing_selected_total",
    "ModelRouter decisions that selected (or mock-selected) a model",
    ["agent_name", "provider", "model_tier", "decision"],
)
LLM_MODEL_ROUTING_BLOCKED_TOTAL = Counter(
    "llm_model_routing_blocked_total",
    "ModelRouter decisions that blocked (per reason)",
    ["agent_name", "reason"],
)
LLM_MODEL_ROUTING_FALLBACK_TOTAL = Counter(
    "llm_model_routing_fallback_total",
    "ModelRouter decisions that used a fallback model",
    ["agent_name", "model_tier"],
)
LLM_MODEL_ROUTING_HUMAN_REVIEW_TOTAL = Counter(
    "llm_model_routing_human_review_total",
    "ModelRouter decisions that flagged requires_human_review=true",
    ["agent_name", "capability"],
)
LLM_MODEL_ROUTING_BUDGET_BLOCKED_TOTAL = Counter(
    "llm_model_routing_budget_blocked_total",
    "ModelRouter decisions blocked by budget gate (Stage 35)",
    ["agent_name", "provider"],
)
LLM_MODEL_POLICY_MISSING_TOTAL = Counter(
    "llm_model_policy_missing_total",
    "ModelRouter calls that landed without an active policy",
    ["agent_name", "capability"],
)
LLM_MODEL_DIRECT_SELECTION_REJECTED_TOTAL = Counter(
    "llm_model_direct_selection_rejected_total",
    "ModelRouter requests carrying an unauthorised requested_model_alias",
    ["agent_name", "capability"],
)

# Stage 40 -- Incident Response & External Alert Receiver metrics.
INCIDENT_ALERTS_RECEIVED_TOTAL = Counter(
    "incident_alerts_received_total",
    "Alert payloads received by the alert receiver",
    ["source", "source_type"],
)
INCIDENT_ALERTS_REJECTED_TOTAL = Counter(
    "incident_alerts_rejected_total",
    "Alert payloads rejected (bad auth, malformed, suppressed)",
    ["reason"],
)
INCIDENT_CREATED_TOTAL = Counter(
    "incident_created_total",
    "New incidents created",
    ["severity", "source"],
)
INCIDENT_DEDUPLICATED_TOTAL = Counter(
    "incident_deduplicated_total",
    "Alerts linked to existing incident via dedupe",
    ["severity"],
)
INCIDENT_ACKNOWLEDGED_TOTAL = Counter(
    "incident_acknowledged_total",
    "Incident acknowledgements",
    ["severity"],
)
INCIDENT_RESOLVED_TOTAL = Counter(
    "incident_resolved_total",
    "Incidents resolved",
    ["severity"],
)
INCIDENT_CLOSED_TOTAL = Counter(
    "incident_closed_total",
    "Incidents closed",
    ["severity"],
)
INCIDENT_ESCALATION_DRY_RUN_TOTAL = Counter(
    "incident_escalation_dry_run_total",
    "Escalation dry-run records written (no real escalation)",
    ["severity", "dry_run"],
)
INCIDENT_POSTMORTEM_REQUIRED_TOTAL = Counter(
    "incident_postmortem_required_total",
    "Incidents flagged as requiring a postmortem",
    ["severity"],
)


# Stage 42 -- audit chain forensics + controlled integrity repair metrics.
AUDIT_CHAIN_FORENSICS_RUNS_TOTAL = Counter(
    "audit_chain_forensics_runs_total",
    "Forensic analyzer runs executed (per root_cause + status)",
    ["root_cause", "status"],
)
AUDIT_CHAIN_FORENSICS_FAILURES_TOTAL = Counter(
    "audit_chain_forensics_failures_total",
    "Forensic analyzer runs that errored (per reason)",
    ["reason"],
)
AUDIT_CHAIN_FAILED_RECORDS_TOTAL = Counter(
    "audit_chain_failed_records_total",
    "Failed integrity records observed by the forensic analyzer (per root_cause)",
    ["root_cause"],
)
AUDIT_CHAIN_REPAIR_DRY_RUN_TOTAL = Counter(
    "audit_chain_repair_dry_run_total",
    "Audit chain repair dry-runs executed (per root_cause + repair_allowed)",
    ["root_cause", "repair_allowed"],
)
AUDIT_CHAIN_REPAIR_SKIPPED_UNSAFE_TOTAL = Counter(
    "audit_chain_repair_skipped_unsafe_total",
    "Audit chain repairs skipped as unsafe / unapproved (per status)",
    ["status"],
)
AUDIT_CHAIN_REPAIR_RUNS_TOTAL = Counter(
    "audit_chain_repair_runs_total",
    "Audit chain repair apply runs (per root_cause + status)",
    ["root_cause", "status"],
)
AUDIT_CHAIN_REPAIR_FAILURES_TOTAL = Counter(
    "audit_chain_repair_failures_total",
    "Audit chain repair applies that failed verification and rolled back",
    ["reason"],
)
AUDIT_CHAIN_REPAIR_RECORDS_CHANGED_TOTAL = Counter(
    "audit_chain_repair_records_changed_total",
    "Integrity records changed by a completed repair (per root_cause)",
    ["root_cause"],
)


# Stage 43 -- controlled audit_log restore exception (test-tamper residue).
AUDIT_LOG_RESTORE_PRECHECK_TOTAL = Counter(
    "audit_log_restore_precheck_total",
    "Audit log restore prechecks executed (per status + root_cause)",
    ["status", "root_cause"],
)
AUDIT_LOG_RESTORE_DRY_RUN_TOTAL = Counter(
    "audit_log_restore_dry_run_total",
    "Audit log restore dry-runs executed (per root_cause)",
    ["root_cause"],
)
AUDIT_LOG_RESTORE_APPROVAL_REQUIRED_TOTAL = Counter(
    "audit_log_restore_approval_required_total",
    "Audit log restore attempts gated awaiting operator approval",
    ["root_cause"],
)
AUDIT_LOG_RESTORE_RUNS_TOTAL = Counter(
    "audit_log_restore_runs_total",
    "Audit log restore apply runs (per status + approved)",
    ["status", "approved"],
)
AUDIT_LOG_RESTORE_FAILURES_TOTAL = Counter(
    "audit_log_restore_failures_total",
    "Audit log restore applies that failed and rolled back (per reason)",
    ["reason"],
)
AUDIT_LOG_RESTORE_VERIFIED_TOTAL = Counter(
    "audit_log_restore_verified_total",
    "Audit log restores whose post-restore verifier passed",
    ["root_cause"],
)
AUDIT_LOG_RESTORE_RECORDS_MODIFIED_TOTAL = Counter(
    "audit_log_restore_records_modified_total",
    "audit_logs rows modified by a restore (must be exactly one per run)",
    ["status"],
)


# Stage 44 -- audit-touching regression serialization + tamper sim isolation.
AUDIT_VERIFICATION_LOCK_ACQUIRED_TOTAL = Counter(
    "audit_verification_lock_acquired_total",
    "Audit verification lock acquisitions (per script + status)",
    ["script_name", "status"],  # status: acquired | inherited
)
AUDIT_VERIFICATION_LOCK_TIMEOUT_TOTAL = Counter(
    "audit_verification_lock_timeout_total",
    "Audit verification lock acquisitions that timed out",
    ["script_name"],
)
AUDIT_VERIFICATION_LOCK_WAIT_SECONDS = Histogram(
    "audit_verification_lock_wait_seconds",
    "Seconds spent waiting for the audit verification lock",
    buckets=(0.01, 0.1, 0.5, 1, 5, 15, 30, 60, 120, 300),
)
AUDIT_TAMPER_SIMULATION_RUNS_TOTAL = Counter(
    "audit_tamper_simulation_runs_total",
    "Tamper simulation runs (per status)",
    ["status"],  # completed | failed
)
AUDIT_TAMPER_SIMULATION_RESTORE_FAILURES_TOTAL = Counter(
    "audit_tamper_simulation_restore_failures_total",
    "Tamper simulations whose restore step failed (residue risk)",
    ["status"],
)
AUDIT_TAMPER_RESIDUE_DETECTED_TOTAL = Counter(
    "audit_tamper_residue_detected_total",
    "Tamper residue detector runs that found residue (per status)",
    ["status"],  # detected | absent
)
AUDIT_TOUCHING_REGRESSION_SERIALIZED_TOTAL = Counter(
    "audit_touching_regression_serialized_total",
    "Full regression runs that serialized audit-touching scripts under the lock",
    ["status"],
)


# ---------------------------------------------------------------------------
# Stage 45 -- Project Planner & Task Graph Orchestration.
# ---------------------------------------------------------------------------
PROJECT_PLANNING_RUNS_TOTAL = Counter(
    "project_planning_runs_total",
    "Project planning runs",
    ["project_type", "status"],
)
PROJECT_PLANNING_FAILURES_TOTAL = Counter(
    "project_planning_failures_total",
    "Project planning runs that failed",
    ["project_type"],
)
PROJECT_TASK_GRAPH_NODES_TOTAL = Counter(
    "project_task_graph_nodes_total",
    "Work-item nodes created across project graphs",
    ["project_type"],
)
PROJECT_TASK_GRAPH_EDGES_TOTAL = Counter(
    "project_task_graph_edges_total",
    "Dependency edges created across project graphs",
    ["project_type"],
)
PROJECT_TASK_GRAPH_VALIDATION_FAILURES_TOTAL = Counter(
    "project_task_graph_validation_failures_total",
    "Task graph validations that did not return valid",
    ["validation_status"],
)
PROJECT_WORK_ITEMS_CREATED_TOTAL = Counter(
    "project_work_items_created_total",
    "Work items persisted",
    ["project_type"],
)
PROJECT_ACCEPTANCE_CRITERIA_CREATED_TOTAL = Counter(
    "project_acceptance_criteria_created_total",
    "Acceptance criteria persisted",
    ["project_type"],
)
PROJECT_DELIVERY_READINESS_CHECKS_TOTAL = Counter(
    "project_delivery_readiness_checks_total",
    "Delivery-readiness evaluations",
    ["status"],
)


# ---------------------------------------------------------------------------
# Stage 46 -- Agent Discussion & Design Review Protocol.
# ---------------------------------------------------------------------------
AGENT_DISCUSSION_SESSIONS_TOTAL = Counter(
    "agent_discussion_sessions_total",
    "Agent discussion sessions",
    ["status"],
)
AGENT_DISCUSSION_CONTRIBUTIONS_TOTAL = Counter(
    "agent_discussion_contributions_total",
    "Agent discussion contributions recorded",
    ["review_type"],
)
DESIGN_REVIEW_SESSIONS_TOTAL = Counter(
    "design_review_sessions_total",
    "Design review sessions",
    ["review_type", "status"],
)
DESIGN_REVIEW_FINDINGS_TOTAL = Counter(
    "design_review_findings_total",
    "Design review findings",
    ["severity"],
)
DESIGN_REVIEW_BLOCKING_FINDINGS_TOTAL = Counter(
    "design_review_blocking_findings_total",
    "Design review blocking (high/critical) findings",
    ["severity"],
)
DESIGN_REVIEW_GATES_EVALUATED_TOTAL = Counter(
    "design_review_gates_evaluated_total",
    "Design review gates evaluated",
    ["status"],
)
DESIGN_REVIEW_GO_NO_GO_TOTAL = Counter(
    "design_review_go_no_go_total",
    "Design review go/no-go decisions",
    ["decision"],
)
ACCEPTANCE_COVERAGE_CHECKS_TOTAL = Counter(
    "acceptance_coverage_checks_total",
    "Acceptance coverage evaluations",
    ["status"],
)


# ---------------------------------------------------------------------------
# Stage 47 -- Real Repo Workspace Operator v1.
# ---------------------------------------------------------------------------
WORKSPACE_EXECUTION_RUNS_TOTAL = Counter(
    "workspace_execution_runs_total",
    "Controlled workspace executions started",
    ["workspace_type", "generation_mode", "status"],
)
WORKSPACE_EXECUTION_FAILURES_TOTAL = Counter(
    "workspace_execution_failures_total",
    "Controlled workspace executions that ended failed/blocked",
    ["status"],
)
WORKSPACE_FILES_GENERATED_TOTAL = Counter(
    "workspace_files_generated_total",
    "Files generated across controlled workspaces",
    ["workspace_type"],
)
WORKSPACE_TESTS_RUNS_TOTAL = Counter(
    "workspace_tests_runs_total",
    "Workspace test runs executed",
    ["test_type", "status"],
)
WORKSPACE_TESTS_PASSED_TOTAL = Counter(
    "workspace_tests_passed_total",
    "Workspace test runs that passed",
    ["test_type"],
)
WORKSPACE_TESTS_FAILED_TOTAL = Counter(
    "workspace_tests_failed_total",
    "Workspace test runs that failed",
    ["test_type"],
)
WORKSPACE_STATIC_CHECKS_TOTAL = Counter(
    "workspace_static_checks_total",
    "Workspace static checks executed",
    ["test_type", "status"],
)
WORKSPACE_DIFF_SUMMARIES_TOTAL = Counter(
    "workspace_diff_summaries_total",
    "Workspace diff summaries produced",
    ["workspace_type"],
)
WORKSPACE_SAFETY_BLOCKS_TOTAL = Counter(
    "workspace_safety_blocks_total",
    "Workspace executions blocked by a safety precondition",
    ["reason"],
)


# ---------------------------------------------------------------------------
# Stage 48 -- Mini Project Delivery Pilot.
# ---------------------------------------------------------------------------
MINI_DELIVERY_PILOT_RUNS_TOTAL = Counter(
    "mini_delivery_pilot_runs_total",
    "Mini delivery pilot runs",
    ["pilot_type", "status"],
)
MINI_DELIVERY_PILOT_FAILURES_TOTAL = Counter(
    "mini_delivery_pilot_failures_total",
    "Mini delivery pilot runs that failed/blocked",
    ["pilot_type"],
)
MINI_DELIVERY_PILOT_STEPS_TOTAL = Counter(
    "mini_delivery_pilot_steps_total",
    "Mini delivery pilot steps recorded",
    ["step_type", "status"],
)
MINI_DELIVERY_ACCEPTANCE_CRITERIA_TOTAL = Counter(
    "mini_delivery_acceptance_criteria_total",
    "Acceptance criteria evaluated across pilots",
    ["pilot_type"],
)
MINI_DELIVERY_ACCEPTANCE_SATISFIED_TOTAL = Counter(
    "mini_delivery_acceptance_satisfied_total",
    "Acceptance criteria evaluated satisfied",
    ["pilot_type"],
)
MINI_DELIVERY_ACCEPTANCE_FAILED_TOTAL = Counter(
    "mini_delivery_acceptance_failed_total",
    "Acceptance criteria evaluated failed",
    ["pilot_type"],
)
MINI_DELIVERY_QA_REPORTS_TOTAL = Counter(
    "mini_delivery_qa_reports_total",
    "QA evidence reports produced",
    ["status"],
)
MINI_DELIVERY_SAFETY_REPORTS_TOTAL = Counter(
    "mini_delivery_safety_reports_total",
    "Safety evidence reports produced",
    ["status"],
)
MINI_DELIVERY_REPORTS_TOTAL = Counter(
    "mini_delivery_reports_total",
    "Mini delivery pilot reports produced",
    ["status"],
)


# ---------------------------------------------------------------------------
# Stage 49 -- Delivery Package & Acceptance Gate.
# ---------------------------------------------------------------------------
DELIVERY_PACKAGE_BUILDS_TOTAL = Counter(
    "delivery_package_builds_total",
    "Delivery package builds",
    ["package_type", "status"],
)
DELIVERY_PACKAGE_BUILD_FAILURES_TOTAL = Counter(
    "delivery_package_build_failures_total",
    "Delivery package builds that failed/blocked",
    ["package_type"],
)
DELIVERY_PACKAGE_SECTIONS_TOTAL = Counter(
    "delivery_package_sections_total",
    "Delivery package sections created",
    ["status"],
)
ACCEPTANCE_GATE_RUNS_TOTAL = Counter(
    "acceptance_gate_runs_total",
    "Acceptance gate runs",
    ["status", "decision"],
)
ACCEPTANCE_GATE_CHECKS_TOTAL = Counter(
    "acceptance_gate_checks_total",
    "Acceptance gate checks evaluated",
    ["check_type", "status"],
)
ACCEPTANCE_GATE_FAILURES_TOTAL = Counter(
    "acceptance_gate_failures_total",
    "Acceptance gate runs that blocked/failed",
    ["decision"],
)
DELIVERY_PACKAGE_READY_FOR_REVIEW_TOTAL = Counter(
    "delivery_package_ready_for_review_total",
    "Delivery packages marked ready_for_review",
    ["package_type"],
)
HANDOFF_SUMMARIES_CREATED_TOTAL = Counter(
    "handoff_summaries_created_total",
    "Handoff summaries created",
    ["summary_type"],
)
DELIVERY_READINESS_SNAPSHOTS_TOTAL = Counter(
    "delivery_readiness_snapshots_total",
    "Delivery readiness snapshots created",
    ["readiness_status"],
)
OPERATOR_ACCEPTANCE_REVIEWS_TOTAL = Counter(
    "operator_acceptance_reviews_total",
    "Operator acceptance review placeholders created",
    ["review_status"],
)


def metrics_response() -> tuple[bytes, str]:
    """Render the default Prometheus registry as (body, content_type)."""
    return generate_latest(), CONTENT_TYPE_LATEST


def install_metrics_endpoint(app) -> None:
    """Attach the /metrics endpoint to a FastAPI app."""
    from fastapi.responses import Response

    @app.get("/metrics")
    def _metrics():
        data, content_type = metrics_response()
        return Response(content=data, media_type=content_type)
