-- Step 66C.1 -- Agent Workroom & Clarification data/API foundation.
--
-- Two new tables, additive only (no change to operator_tasks or any other
-- existing table): task_messages (workroom messages, including clarification
-- questions/answers as specific message_type values) and clarification_requests
-- (the clarification lifecycle: open -> answered/expired/canceled).
--
-- Message/question/answer bodies are stored as plain TEXT only -- never rendered
-- as HTML, never executed as markdown/template/script. Length-limited at the DB
-- layer (defense in depth alongside the Pydantic Field(max_length=...) checks in
-- shared/sdk/tasks/workroom_models.py). No row here ever triggers a workflow
-- dispatch or resume. Idempotent / re-runnable.

BEGIN;

CREATE TABLE IF NOT EXISTS task_messages (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id               UUID NOT NULL REFERENCES operator_tasks(id),
    correlation_id        UUID NOT NULL DEFAULT uuid_generate_v4(),
    sender_type           TEXT NOT NULL,
    sender_id             TEXT NOT NULL,
    sender_role           TEXT,
    message_type          TEXT NOT NULL,
    body                  TEXT NOT NULL,
    visibility            TEXT NOT NULL DEFAULT 'task_participants',
    reply_to_message_id   UUID REFERENCES task_messages(id),
    audit_ref             TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_task_messages_sender_type CHECK (sender_type IN (
        'human', 'agent', 'system', 'audit'
    )),
    CONSTRAINT chk_task_messages_message_type CHECK (message_type IN (
        'human_message', 'agent_message', 'clarification_question', 'clarification_answer',
        'system_event', 'audit_event', 'delivery_comment', 'request_changes_note',
        'qa_result_note', 'approval_request_note'
    )),
    CONSTRAINT chk_task_messages_visibility CHECK (visibility IN (
        'task_participants', 'operators', 'audit_only', 'private_system'
    )),
    -- Message body safety (security addendum 3.2): plain text only, length-limited.
    CONSTRAINT chk_task_messages_body_nonempty CHECK (length(btrim(body)) > 0),
    CONSTRAINT chk_task_messages_body_length CHECK (length(body) <= 8000)
);

CREATE INDEX IF NOT EXISTS idx_task_messages_task_id ON task_messages (task_id);
CREATE INDEX IF NOT EXISTS idx_task_messages_created_at ON task_messages (created_at);
CREATE INDEX IF NOT EXISTS idx_task_messages_message_type ON task_messages (message_type);

CREATE TABLE IF NOT EXISTS clarification_requests (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id               UUID NOT NULL REFERENCES operator_tasks(id),
    question_message_id   UUID NOT NULL REFERENCES task_messages(id),
    status                TEXT NOT NULL DEFAULT 'open',
    question              TEXT NOT NULL,
    requested_by_type     TEXT NOT NULL,
    requested_by_id       TEXT NOT NULL,
    assigned_to           TEXT,
    due_at                TIMESTAMPTZ NOT NULL,
    reminder_at           TIMESTAMPTZ NOT NULL,
    answered_at           TIMESTAMPTZ,
    answer_message_id     UUID REFERENCES task_messages(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_clarification_requests_status CHECK (status IN (
        'open', 'answered', 'expired', 'canceled'
    )),
    CONSTRAINT chk_clarification_requests_question_nonempty CHECK (length(btrim(question)) > 0),
    CONSTRAINT chk_clarification_requests_question_length CHECK (length(question) <= 4000)
);

CREATE INDEX IF NOT EXISTS idx_clarification_requests_task_id ON clarification_requests (task_id);
CREATE INDEX IF NOT EXISTS idx_clarification_requests_status ON clarification_requests (status);

COMMIT;
