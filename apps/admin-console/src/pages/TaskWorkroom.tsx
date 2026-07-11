// Step 66C.2 -- Task-level Agent Workroom page (/tasks/:taskId/workroom).
// Step 66C.2-R -- added the Create Clarification form (operator validation
// found no way to raise a clarification from the UI at all -- a typed
// question only ever became a normal message; see
// docs/test/step66c2-remediation-report.md). "Send Message" and "Create
// Clarification" are now two clearly separate actions; posting a normal
// message never turns it into a clarification.
//
// SAFETY: messages/questions/answers are rendered as PLAIN TEXT ONLY -- via
// ordinary React text-content interpolation ({m.body}); React's raw-HTML
// escape hatch is never used, no markdown-to-HTML rendering, no URL
// auto-linking. dispatch_enabled / resume_dispatch_enabled are always read
// from the API response (never hardcoded) and are always false -- no workflow
// dispatch or resume path exists anywhere in this stage.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AsyncView } from "../components/AsyncView";
import { StatusBadge } from "../components/StatusBadge";
import { TestRoleBanner } from "../tasks/TestRoleBanner";
import { workroomApi, WorkroomApiError } from "../tasks/workroomClient";
import {
  CLARIFICATION_ANSWER_MAX_LENGTH,
  CLARIFICATION_QUESTION_MAX_LENGTH,
  MESSAGE_BODY_MAX_LENGTH,
} from "../tasks/workroomTypes";
import type { ClarificationRequest, TaskMessage, WorkroomResponse } from "../tasks/workroomTypes";

export function TaskWorkroom() {
  const { taskId = "" } = useParams();
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <>
      <h2>Workroom</h2>
      <p className="note">
        <Link to={`/tasks/${taskId}`}>&larr; Back to task detail</Link>
      </p>
      <p className="note">
        Task-level Agent Workroom (Step 66C.2). Messages are rendered as plain text only. No
        workflow dispatch or resume occurs from this page.
      </p>
      <TestRoleBanner />
      <AsyncView key={refreshKey} load={() => workroomApi.get(taskId)}>
        {(data: WorkroomResponse) => (
          <WorkroomContent
            taskId={taskId}
            data={data}
            onChanged={() => setRefreshKey((k) => k + 1)}
          />
        )}
      </AsyncView>
    </>
  );
}

function WorkroomContent({
  taskId,
  data,
  onChanged,
}: {
  taskId: string;
  data: WorkroomResponse;
  onChanged: () => void;
}) {
  return (
    <>
      <div className="safety-panel" data-testid="workroom-safety-panel">
        <h3>Safety</h3>
        <ul>
          <li>
            Task status: <StatusBadge value={data.task_status} />
          </li>
          <li data-testid="workroom-dispatch-enabled">
            dispatch_enabled: <StatusBadge value={data.dispatch_enabled} /> (no workflow dispatch
            occurs in this stage)
          </li>
          <li data-testid="workroom-resume-dispatch-enabled">
            resume_dispatch_enabled: <StatusBadge value={data.resume_dispatch_enabled} />{" "}
            (answering a clarification never resumes a workflow)
          </li>
        </ul>
      </div>
      <MessageList messages={data.messages} />
      <MessageComposer taskId={taskId} onPosted={onChanged} />
      <ClarificationList
        taskId={taskId}
        clarifications={data.clarification_requests}
        onAnswered={onChanged}
        onCreated={onChanged}
      />
    </>
  );
}

function MessageList({ messages }: { messages: TaskMessage[] }) {
  return (
    <div className="workroom-section">
      <h3>Messages</h3>
      {!messages.length && <div className="empty">No messages yet</div>}
      {messages.length > 0 && (
        <ul className="workroom-messages" data-testid="workroom-messages">
          {messages.map((m) => (
            <li key={m.id} className="workroom-message" data-testid="workroom-message">
              <div className="workroom-message-meta">
                <span className="badge b-neutral">{m.message_type}</span> <strong>{m.sender_type}</strong>
                {m.sender_role ? ` (${m.sender_role})` : ""} — {m.sender_id} &middot; {m.created_at}
                {" "}
                &middot; visibility: {m.visibility}
                {m.audit_ref ? ` · audit_ref: ${m.audit_ref}` : ""}
              </div>
              {/* Plain text only -- React text interpolation, no HTML rendering. */}
              <p className="workroom-message-body">{m.body}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MessageComposer({ taskId, onPosted }: { taskId: string; onPosted: () => void }) {
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handlePost(): Promise<void> {
    setFieldError(null);
    setError(null);
    const trimmed = body.trim();
    if (!trimmed) {
      setFieldError("Message body is required.");
      return;
    }
    if (trimmed.length > MESSAGE_BODY_MAX_LENGTH) {
      setFieldError(`Message body must be ${MESSAGE_BODY_MAX_LENGTH} characters or fewer.`);
      return;
    }
    setSubmitting(true);
    try {
      await workroomApi.postMessage(taskId, trimmed);
      setBody("");
      onPosted();
    } catch (e) {
      setError(
        e instanceof WorkroomApiError ? e.message : e instanceof Error ? e.message : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="workroom-composer" data-testid="workroom-composer">
      <h3>Send Message</h3>
      <p className="note">
        A normal workroom message. It does not require an answer and does not change the task
        status. To ask a question that needs a required human answer, use{" "}
        <strong>Create Clarification</strong> below instead.
      </p>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        maxLength={MESSAGE_BODY_MAX_LENGTH}
        placeholder="Write a message to the workroom..."
        data-testid="workroom-message-input"
      />
      <p className="note">
        {body.length} / {MESSAGE_BODY_MAX_LENGTH} characters
      </p>
      {fieldError && (
        <div className="error" data-testid="workroom-message-field-error">
          {fieldError}
        </div>
      )}
      {error && (
        <div className="error" data-testid="workroom-message-error">
          {error}
        </div>
      )}
      <button disabled={submitting} onClick={() => void handlePost()} data-testid="workroom-post-message">
        Send Message
      </button>
    </div>
  );
}

function ClarificationList({
  taskId,
  clarifications,
  onAnswered,
  onCreated,
}: {
  taskId: string;
  clarifications: ClarificationRequest[];
  onAnswered: () => void;
  onCreated: () => void;
}) {
  return (
    <div className="workroom-section" data-testid="workroom-clarifications">
      <h3>Clarifications</h3>
      <CreateClarificationForm taskId={taskId} onCreated={onCreated} />
      {!clarifications.length && <div className="empty">No clarification requests</div>}
      {clarifications.map((c) => (
        <ClarificationCard key={c.id} taskId={taskId} clarification={c} onAnswered={onAnswered} />
      ))}
    </div>
  );
}

function CreateClarificationForm({
  taskId,
  onCreated,
}: {
  taskId: string;
  onCreated: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(): Promise<void> {
    setFieldError(null);
    setError(null);
    const trimmed = question.trim();
    if (!trimmed) {
      setFieldError("Question is required.");
      return;
    }
    if (trimmed.length > CLARIFICATION_QUESTION_MAX_LENGTH) {
      setFieldError(`Question must be ${CLARIFICATION_QUESTION_MAX_LENGTH} characters or fewer.`);
      return;
    }
    setSubmitting(true);
    try {
      await workroomApi.createClarification(taskId, trimmed, assignedTo.trim() || undefined);
      setQuestion("");
      setAssignedTo("");
      onCreated();
    } catch (e) {
      setError(
        e instanceof WorkroomApiError ? e.message : e instanceof Error ? e.message : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="workroom-create-clarification" data-testid="workroom-create-clarification">
      <h4>Create Clarification</h4>
      <p className="note">
        Ask a question that requires a human answer before this task can proceed. This moves the
        task to <code>clarification_needed</code> and is separate from a normal message.
      </p>
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        maxLength={CLARIFICATION_QUESTION_MAX_LENGTH}
        placeholder="What do you need clarified?"
        data-testid="workroom-clarification-question-input"
      />
      <p className="note">
        {question.length} / {CLARIFICATION_QUESTION_MAX_LENGTH} characters
      </p>
      <input
        type="text"
        value={assignedTo}
        onChange={(e) => setAssignedTo(e.target.value)}
        placeholder="Assigned to (optional)"
        data-testid="workroom-clarification-assigned-to-input"
      />
      {fieldError && (
        <div className="error" data-testid="workroom-create-clarification-field-error">
          {fieldError}
        </div>
      )}
      {error && (
        <div className="error" data-testid="workroom-create-clarification-error">
          {error}
        </div>
      )}
      <button
        disabled={submitting}
        onClick={() => void handleCreate()}
        data-testid="workroom-submit-create-clarification"
      >
        Create Clarification
      </button>
    </div>
  );
}

function ClarificationCard({
  taskId,
  clarification,
  onAnswered,
}: {
  taskId: string;
  clarification: ClarificationRequest;
  onAnswered: () => void;
}) {
  return (
    <div className="card workroom-clarification" data-testid="workroom-clarification-card">
      <p>
        Status: <StatusBadge value={clarification.status} />
      </p>
      {/* Plain text only -- React text interpolation, no HTML rendering. */}
      <p className="workroom-message-body" data-testid="workroom-clarification-question">
        {clarification.question}
      </p>
      <p className="note">
        Requested by {clarification.requested_by_id} ({clarification.requested_by_type})
        {clarification.assigned_to ? ` · assigned to ${clarification.assigned_to}` : ""}
      </p>
      <p className="note">
        Reminder at: {clarification.reminder_at} &middot; Due at: {clarification.due_at}
      </p>
      {clarification.answered_at && (
        <p className="note" data-testid="workroom-clarification-answered-at">
          Answered at: {clarification.answered_at}
        </p>
      )}
      {clarification.status === "open" && (
        <AnswerForm taskId={taskId} clarificationId={clarification.id} onAnswered={onAnswered} />
      )}
    </div>
  );
}

function AnswerForm({
  taskId,
  clarificationId,
  onAnswered,
}: {
  taskId: string;
  clarificationId: string;
  onAnswered: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAnswer(): Promise<void> {
    setFieldError(null);
    setError(null);
    const trimmed = answer.trim();
    if (!trimmed) {
      setFieldError("Answer is required.");
      return;
    }
    if (trimmed.length > CLARIFICATION_ANSWER_MAX_LENGTH) {
      setFieldError(`Answer must be ${CLARIFICATION_ANSWER_MAX_LENGTH} characters or fewer.`);
      return;
    }
    setSubmitting(true);
    try {
      await workroomApi.answerClarification(taskId, clarificationId, trimmed);
      setAnswer("");
      onAnswered();
    } catch (e) {
      setError(
        e instanceof WorkroomApiError ? e.message : e instanceof Error ? e.message : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="workroom-answer-form" data-testid="workroom-answer-form">
      <textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        maxLength={CLARIFICATION_ANSWER_MAX_LENGTH}
        placeholder="Write your answer..."
        data-testid="workroom-answer-input"
      />
      <p className="note">
        {answer.length} / {CLARIFICATION_ANSWER_MAX_LENGTH} characters
      </p>
      {fieldError && (
        <div className="error" data-testid="workroom-answer-field-error">
          {fieldError}
        </div>
      )}
      {error && (
        <div className="error" data-testid="workroom-answer-error">
          {error}
        </div>
      )}
      <button
        disabled={submitting}
        onClick={() => void handleAnswer()}
        data-testid="workroom-submit-answer"
      >
        Submit Answer
      </button>
    </div>
  );
}
