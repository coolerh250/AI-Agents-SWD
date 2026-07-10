"""Step 66C.1 -- Agent Workroom & Clarification request/response models.

Message/question/answer bodies are treated as untrusted plain text: no HTML,
markdown, template, or script execution is ever performed on them (security
addendum 3.2/3.3). Length limits are enforced here (Pydantic) and again at the
DB layer (migrations/030_workroom_clarification_foundation.sql) as defense in
depth. Rendering these fields as HTML is out of scope for 66C.1 (no UI in this
stage) and is a mandatory constraint for the future 66C.2 UI.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SenderType = Literal["human", "agent", "system", "audit"]

MessageType = Literal[
    "human_message",
    "agent_message",
    "clarification_question",
    "clarification_answer",
    "system_event",
    "audit_event",
    "delivery_comment",
    "request_changes_note",
    "qa_result_note",
    "approval_request_note",
]

Visibility = Literal["task_participants", "operators", "audit_only", "private_system"]

ClarificationStatus = Literal["open", "answered", "expired", "canceled"]

# Security addendum 3.2 -- minimum recommended limits, enforced here + in the DB CHECK constraints.
MESSAGE_BODY_MAX_LENGTH = 8000
CLARIFICATION_QUESTION_MAX_LENGTH = 4000
# The clarification answer is stored as a task_messages.body row (message_type
# "clarification_answer"), so it shares the same 8000-char body limit above.
CLARIFICATION_ANSWER_MAX_LENGTH = MESSAGE_BODY_MAX_LENGTH

# Operator decision (66A.3 D4 / Q2): 24h reminder / 72h due, project-configurable
# in later stages -- fixed defaults only in 66C.1.
CLARIFICATION_REMINDER_HOURS = 24
CLARIFICATION_DUE_HOURS = 72


class WorkroomMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=MESSAGE_BODY_MAX_LENGTH)


class TaskMessage(BaseModel):
    id: UUID
    task_id: UUID
    correlation_id: UUID
    sender_type: SenderType
    sender_id: str
    sender_role: str | None = None
    message_type: MessageType
    body: str
    visibility: Visibility
    reply_to_message_id: UUID | None = None
    audit_ref: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ClarificationCreate(BaseModel):
    question: str = Field(min_length=1, max_length=CLARIFICATION_QUESTION_MAX_LENGTH)
    assigned_to: str | None = None


class ClarificationAnswerCreate(BaseModel):
    answer: str = Field(min_length=1, max_length=CLARIFICATION_ANSWER_MAX_LENGTH)


class ClarificationRequest(BaseModel):
    id: UUID
    task_id: UUID
    question_message_id: UUID
    status: ClarificationStatus
    question: str
    requested_by_type: str
    requested_by_id: str
    assigned_to: str | None = None
    due_at: str | None = None
    reminder_at: str | None = None
    answered_at: str | None = None
    answer_message_id: UUID | None = None
    created_at: str | None = None
    updated_at: str | None = None


__all__ = [
    "SenderType",
    "MessageType",
    "Visibility",
    "ClarificationStatus",
    "MESSAGE_BODY_MAX_LENGTH",
    "CLARIFICATION_QUESTION_MAX_LENGTH",
    "CLARIFICATION_ANSWER_MAX_LENGTH",
    "CLARIFICATION_REMINDER_HOURS",
    "CLARIFICATION_DUE_HOURS",
    "WorkroomMessageCreate",
    "TaskMessage",
    "ClarificationCreate",
    "ClarificationAnswerCreate",
    "ClarificationRequest",
]
