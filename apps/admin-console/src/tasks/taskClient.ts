// Step 66B.2 -- task-assignment API client.
//
// SAFETY: this client exposes ONLY explicit, named, typed methods against the
// /tasks API (Step 66B.1). There is no generic verb+URL helper. Every call sends
// the fail-closed test-only X-Task-Actor / X-Task-Role headers (see testRole.ts).
// No workflow is ever dispatched from this client -- it only creates / lists /
// reads / submits task records; the backend guarantees dispatch_enabled=false.

import { API_BASE } from "../api/client";
import { getTestRole } from "./testRole";
import type { Task, TaskCreate, TaskListFilters, TaskListResponse } from "./taskTypes";

const TASKS = API_BASE + "/tasks";

export class TaskApiError extends Error {
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

// Step 66B.3 -- readable RBAC/auth error messages (safety UX hardening). Falls
// back to the raw backend detail code for anything not mapped here.
const READABLE_ERRORS: Record<string, string> = {
  task_api_test_auth_disabled: "Task API test-auth is disabled in this environment.",
  missing_actor: "Missing actor identity — set a test actor in the role banner.",
  missing_role: "Missing role — select a role in the role banner.",
  invalid_role: "Unrecognized role — select a valid role in the role banner.",
  role_cannot_create_task: "Your simulated role cannot create tasks.",
  role_cannot_view_tasks: "Your simulated role cannot view tasks.",
  role_cannot_submit_task: "Your simulated role cannot submit tasks.",
  not_own_task: "You can only access your own tasks with this role.",
  task_not_found: "Task not found.",
};

async function handle<T>(res: Response): Promise<T> {
  const body = await readBody(res);
  if (!res.ok) {
    const detail = detailOf(body);
    const readable = detail ? READABLE_ERRORS[detail] : undefined;
    const message = readable
      ? `${readable} (${detail})`
      : `${detail || "task_api_error"} (HTTP ${res.status})`;
    throw new TaskApiError(message, res.status, detail);
  }
  return body as T;
}

// Private helpers -- not exported; callers use the named taskApi methods only.
async function taskGet<T>(path: string): Promise<T> {
  const res = await fetch(TASKS + path, {
    method: "GET",
    headers: { Accept: "application/json", ...authHeaders() },
  });
  return handle<T>(res);
}

async function taskPost<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const res = await fetch(TASKS + path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(body || {}),
  });
  return handle<T>(res);
}

function filterQuery(filters: TaskListFilters): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) qs.set(key, value);
  }
  const q = qs.toString();
  return q ? `?${q}` : "";
}

export const taskApi = {
  list(filters: TaskListFilters = {}): Promise<TaskListResponse> {
    return taskGet<TaskListResponse>(filterQuery(filters));
  },
  create(payload: TaskCreate): Promise<Task & { dispatch_enabled: boolean }> {
    return taskPost<Task & { dispatch_enabled: boolean }>(
      "",
      payload as unknown as Record<string, unknown>,
    );
  },
  get(id: string): Promise<Task> {
    return taskGet<Task>(`/${id}`);
  },
  submit(id: string): Promise<Task & { dispatch_enabled: boolean }> {
    return taskPost<Task & { dispatch_enabled: boolean }>(`/${id}/submit`);
  },
};
