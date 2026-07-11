// Step 66C.2 -- workroom/clarification API client.
// Step 66C.2-R -- added createClarification() (was deferred in 66C.2; operator
// validation found no way to raise a clarification from the UI at all -- see
// docs/test/step66c2-remediation-report.md).
//
// SAFETY: this client exposes ONLY explicit, named, typed methods against the
// /tasks/{id}/workroom and /tasks/{id}/clarifications endpoints (Step 66C.1).
// There is no generic verb+URL helper. Every call sends the fail-closed
// test-only X-Task-Actor / X-Task-Role headers (see testRole.ts). No workflow
// is ever dispatched or resumed from this client -- the backend guarantees
// dispatch_enabled=false / resume_dispatch_enabled=false on every response.

import { API_BASE } from "../api/client";
import { getTestRole } from "./testRole";
import type { ClarificationRequest, TaskMessage, WorkroomResponse } from "./workroomTypes";

const TASKS = API_BASE + "/tasks";

export class WorkroomApiError extends Error {
  code: number;
  detail?: string;
  constructor(message: string, code: number, detail?: string) {
    super(message);
    this.code = code;
    this.detail = detail;
  }
}

function authHeaders(): Record<string, string> {
  const { actor, role } = getTestRole();
  return { "X-Task-Actor": actor, "X-Task-Role": role };
}

async function readBody(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function detailOf(body: unknown): string | undefined {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail?: unknown }).detail;
    return d === undefined ? undefined : String(d);
  }
  return undefined;
}

// Readable RBAC/auth/state error messages (mirrors taskClient.ts's pattern).
const READABLE_ERRORS: Record<string, string> = {
  task_api_test_auth_disabled: "Task API test-auth is disabled in this environment.",
  missing_actor: "Missing actor identity — set a test actor in the role banner.",
  missing_role: "Missing role — select a role in the role banner.",
  invalid_role: "Unrecognized role — select a valid role in the role banner.",
  role_cannot_view_workroom: "Your simulated role cannot view this workroom.",
  role_cannot_post_message: "Your simulated role cannot post messages here.",
  role_cannot_create_clarification: "Your simulated role cannot create a clarification request.",
  role_cannot_answer_clarification: "Your simulated role cannot answer this clarification.",
  not_own_task: "You can only access your own tasks with this role.",
  task_not_found: "Task not found.",
  clarification_not_found: "Clarification not found.",
};

function readableMessage(detail: string | undefined, status: number): string {
  if (!detail) return `workroom_api_error (HTTP ${status})`;
  const mapped = READABLE_ERRORS[detail];
  if (mapped) return `${mapped} (${detail})`;
  if (detail.startsWith("invalid_state_for_answer:")) {
    return `This clarification has already been answered (${detail}).`;
  }
  return `${detail} (HTTP ${status})`;
}

async function handle<T>(res: Response): Promise<T> {
  const body = await readBody(res);
  if (!res.ok) {
    const detail = detailOf(body);
    throw new WorkroomApiError(readableMessage(detail, res.status), res.status, detail);
  }
  return body as T;
}

async function workroomGet<T>(path: string): Promise<T> {
  const res = await fetch(TASKS + path, {
    method: "GET",
    headers: { Accept: "application/json", ...authHeaders() },
  });
  return handle<T>(res);
}

async function workroomPost<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(TASKS + path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(body),
  });
  return handle<T>(res);
}

export const workroomApi = {
  get(taskId: string): Promise<WorkroomResponse> {
    return workroomGet<WorkroomResponse>(`/${taskId}/workroom`);
  },
  postMessage(
    taskId: string,
    body: string,
  ): Promise<TaskMessage & { dispatch_enabled: boolean }> {
    return workroomPost<TaskMessage & { dispatch_enabled: boolean }>(
      `/${taskId}/workroom/messages`,
      { body },
    );
  },
  createClarification(
    taskId: string,
    question: string,
    assignedTo?: string,
  ): Promise<
    ClarificationRequest & {
      task_status: string;
      dispatch_enabled: boolean;
      resume_dispatch_enabled: boolean;
    }
  > {
    return workroomPost(`/${taskId}/clarifications`, {
      question,
      assigned_to: assignedTo || null,
    });
  },
  answerClarification(
    taskId: string,
    clarificationId: string,
    answer: string,
  ): Promise<
    ClarificationRequest & {
      task_status: string;
      dispatch_enabled: boolean;
      resume_dispatch_enabled: boolean;
    }
  > {
    return workroomPost(`/${taskId}/clarifications/${clarificationId}/answer`, { answer });
  },
};
