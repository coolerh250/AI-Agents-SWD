// Step 66C.2 -- TypeScript types mirroring shared/sdk/tasks/workroom_models.py (Step 66C.1).

export const SENDER_TYPES = ["human", "agent", "system", "audit"] as const;
export type SenderType = (typeof SENDER_TYPES)[number];

export const MESSAGE_TYPES = [
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
] as const;
export type MessageType = (typeof MESSAGE_TYPES)[number];

export const VISIBILITY_VALUES = [
  "task_participants",
  "operators",
  "audit_only",
  "private_system",
] as const;
export type Visibility = (typeof VISIBILITY_VALUES)[number];

export const CLARIFICATION_STATUSES = ["open", "answered", "expired", "canceled"] as const;
export type ClarificationStatus = (typeof CLARIFICATION_STATUSES)[number];

// Step 66C.1 security addendum limits -- must match shared/sdk/tasks/workroom_models.py exactly.
export const MESSAGE_BODY_MAX_LENGTH = 8000;
export const CLARIFICATION_QUESTION_MAX_LENGTH = 4000;
export const CLARIFICATION_ANSWER_MAX_LENGTH = 8000;

export interface TaskMessage {
  id: string;
  task_id: string;
  correlation_id: string;
  sender_type: SenderType;
  sender_id: string;
  sender_role: string | null;
  message_type: MessageType;
  body: string;
  visibility: Visibility;
  reply_to_message_id: string | null;
  audit_ref: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ClarificationRequest {
  id: string;
  task_id: string;
  question_message_id: string;
  status: ClarificationStatus;
  question: string;
  requested_by_type: string;
  requested_by_id: string;
  assigned_to: string | null;
  due_at: string | null;
  reminder_at: string | null;
  answered_at: string | null;
  answer_message_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface WorkroomResponse {
  task_id: string;
  task_status: string;
  messages: TaskMessage[];
  clarification_requests: ClarificationRequest[];
  dispatch_enabled: boolean;
  resume_dispatch_enabled: boolean;
}
