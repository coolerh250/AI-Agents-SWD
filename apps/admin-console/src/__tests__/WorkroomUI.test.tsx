import { describe, it, expect, vi, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { TaskDetail } from "../pages/TaskDetail";
import { TaskWorkroom } from "../pages/TaskWorkroom";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

const SAMPLE_TASK = {
  id: "11111111-1111-1111-1111-111111111111",
  title: "Sample task",
  description: null,
  task_type: "software_delivery",
  priority: "medium",
  status: "intake_review",
  created_by: "test-operator",
  owner: "test-operator",
  project_id: null,
  environment: "test",
  production_effect: false,
  requires_approval: false,
  clarification_status: "open",
  delivery_status: "none",
  intake_planning_only: false,
  correlation_id: "22222222-2222-2222-2222-222222222222",
  metadata: {},
  created_at: "2026-07-10T00:00:00Z",
  updated_at: "2026-07-10T00:00:00Z",
  dispatch_enabled: false,
};

const MALICIOUS_BODY = '<img src=x onerror=alert(1)>';

const SAMPLE_MESSAGE = {
  id: "33333333-3333-3333-3333-333333333333",
  task_id: SAMPLE_TASK.id,
  correlation_id: "44444444-4444-4444-4444-444444444444",
  sender_type: "human",
  sender_id: "alice",
  sender_role: "requester",
  message_type: "human_message",
  body: "Please confirm the target environment.",
  visibility: "task_participants",
  reply_to_message_id: null,
  audit_ref: null,
  created_at: "2026-07-10T00:00:01Z",
  updated_at: "2026-07-10T00:00:01Z",
};

const MALICIOUS_MESSAGE = {
  ...SAMPLE_MESSAGE,
  id: "55555555-5555-5555-5555-555555555555",
  body: MALICIOUS_BODY,
};

const OPEN_CLARIFICATION = {
  id: "66666666-6666-6666-6666-666666666666",
  task_id: SAMPLE_TASK.id,
  question_message_id: "77777777-7777-7777-7777-777777777777",
  status: "open",
  question: "Which environment should this target?",
  requested_by_type: "human",
  requested_by_id: "pm1",
  assigned_to: null,
  due_at: "2026-07-13T00:00:00Z",
  reminder_at: "2026-07-11T00:00:00Z",
  answered_at: null,
  answer_message_id: null,
  created_at: "2026-07-10T00:00:00Z",
  updated_at: "2026-07-10T00:00:00Z",
};

function workroomResponse(overrides: Record<string, unknown> = {}) {
  return {
    task_id: SAMPLE_TASK.id,
    task_status: "clarification_needed",
    messages: [SAMPLE_MESSAGE],
    clarification_requests: [OPEN_CLARIFICATION],
    dispatch_enabled: false,
    resume_dispatch_enabled: false,
    ...overrides,
  };
}

function mockFetchOnce(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });
}

function renderWithRouter(initialEntries: string[]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/tasks/:taskId" element={<TaskDetail />} />
        <Route path="/tasks/:taskId/workroom" element={<TaskWorkroom />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Task Detail -> Open Workroom link", () => {
  it("shows an Open Workroom link on task detail", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(SAMPLE_TASK));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}`]);
    await waitFor(() => expect(screen.getByTestId("open-workroom-link")).toBeDefined());
    expect(screen.getByTestId("open-workroom-link").getAttribute("href")).toBe(
      `/tasks/${SAMPLE_TASK.id}/workroom`,
    );
  });
});

describe("TaskWorkroom page", () => {
  it("renders the workroom page with safety fields from the API response", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(workroomResponse()));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("workroom-safety-panel")).toBeDefined());
    expect(screen.getByTestId("workroom-dispatch-enabled").textContent).toMatch(/false/i);
    expect(screen.getByTestId("workroom-resume-dispatch-enabled").textContent).toMatch(/false/i);
  });

  it("shows the test role simulation banner", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(workroomResponse()));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("test-role-banner")).toBeDefined());
  });

  it("shows an empty state when there are no messages or clarifications", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchOnce(workroomResponse({ messages: [], clarification_requests: [] })),
    );
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByText("No messages yet")).toBeDefined());
    expect(screen.getByText("No clarification requests")).toBeDefined();
  });

  it("shows an error state on server error", async () => {
    vi.stubGlobal("fetch", mockFetchOnce({ detail: "not_own_task" }, 403));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByText(/Unable to load data/)).toBeDefined());
  });

  it("shows a readable RBAC error message", async () => {
    vi.stubGlobal("fetch", mockFetchOnce({ detail: "not_own_task" }, 403));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() =>
      expect(screen.getByText(/You can only access your own tasks with this role/)).toBeDefined(),
    );
  });
});

describe("Message rendering (plain text only)", () => {
  it("renders message body as plain text", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(workroomResponse()));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() =>
      expect(screen.getByText("Please confirm the target environment.")).toBeDefined(),
    );
  });

  it("renders a malicious-looking HTML body as literal text, not as markup", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchOnce(workroomResponse({ messages: [MALICIOUS_MESSAGE] })),
    );
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("workroom-messages")).toBeDefined());
    // The literal string must appear as text content...
    expect(screen.getByText(MALICIOUS_BODY)).toBeDefined();
    // ...and must NOT have been parsed into a real <img> element.
    expect(screen.queryByRole("img")).toBeNull();
    expect(document.querySelector("img")).toBeNull();
  });

  it("renders the clarification question as plain text", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(workroomResponse()));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() =>
      expect(screen.getByTestId("workroom-clarification-question").textContent).toBe(
        OPEN_CLARIFICATION.question,
      ),
    );
  });
});

describe("Message composer", () => {
  it("requires a non-empty body before posting", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(workroomResponse()));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("workroom-composer")).toBeDefined());
    fireEvent.click(screen.getByTestId("workroom-post-message"));
    await waitFor(() => expect(screen.getByTestId("workroom-message-field-error")).toBeDefined());
  });

  it("rejects a body over the 8000-character limit client-side", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(workroomResponse()));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("workroom-composer")).toBeDefined());
    const textarea = screen.getByTestId("workroom-message-input") as HTMLTextAreaElement;
    // maxLength on the textarea itself caps input at 8000 -- verify that cap.
    expect(textarea.maxLength).toBe(8000);
  });

  it("posts a message with the required auth headers and refreshes on success", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => workroomResponse() })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ ...SAMPLE_MESSAGE, dispatch_enabled: false }),
      })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => workroomResponse() });
    vi.stubGlobal("fetch", fetchMock);
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("workroom-composer")).toBeDefined());
    fireEvent.change(screen.getByTestId("workroom-message-input"), {
      target: { value: "New workroom message" },
    });
    fireEvent.click(screen.getByTestId("workroom-post-message"));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
    const [url, init] = fetchMock.mock.calls[1] as [
      string,
      { method: string; headers: Record<string, string>; body: string },
    ];
    expect(String(url)).toContain(`/tasks/${SAMPLE_TASK.id}/workroom/messages`);
    expect(init.method).toBe("POST");
    expect(init.headers["X-Task-Actor"]).toBeTruthy();
    expect(init.headers["X-Task-Role"]).toBeTruthy();
    const body = JSON.parse(init.body) as { body: string };
    expect(body.body).toBe("New workroom message");
  });
});

describe("Clarification answer form", () => {
  it("requires a non-empty answer before submitting", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(workroomResponse()));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("workroom-answer-form")).toBeDefined());
    fireEvent.click(screen.getByTestId("workroom-submit-answer"));
    await waitFor(() => expect(screen.getByTestId("workroom-answer-field-error")).toBeDefined());
  });

  it("caps the answer textarea at 8000 characters", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(workroomResponse()));
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("workroom-answer-form")).toBeDefined());
    const textarea = screen.getByTestId("workroom-answer-input") as HTMLTextAreaElement;
    expect(textarea.maxLength).toBe(8000);
  });

  it("does not show an answer form for an already-answered clarification", async () => {
    const answered = {
      ...OPEN_CLARIFICATION,
      status: "answered",
      answered_at: "2026-07-10T01:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      mockFetchOnce(workroomResponse({ clarification_requests: [answered] })),
    );
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() =>
      expect(screen.getByTestId("workroom-clarification-answered-at")).toBeDefined(),
    );
    expect(screen.queryByTestId("workroom-answer-form")).toBeNull();
  });

  it("submits an answer with the required auth headers and refreshes on success", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => workroomResponse() })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          ...OPEN_CLARIFICATION,
          status: "answered",
          task_status: "intake_review",
          dispatch_enabled: false,
          resume_dispatch_enabled: false,
        }),
      })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => workroomResponse() });
    vi.stubGlobal("fetch", fetchMock);
    renderWithRouter([`/tasks/${SAMPLE_TASK.id}/workroom`]);
    await waitFor(() => expect(screen.getByTestId("workroom-answer-form")).toBeDefined());
    fireEvent.change(screen.getByTestId("workroom-answer-input"), {
      target: { value: "Use the test environment." },
    });
    fireEvent.click(screen.getByTestId("workroom-submit-answer"));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
    const [url, init] = fetchMock.mock.calls[1] as [
      string,
      { method: string; headers: Record<string, string>; body: string },
    ];
    expect(String(url)).toContain(
      `/tasks/${SAMPLE_TASK.id}/clarifications/${OPEN_CLARIFICATION.id}/answer`,
    );
    expect(init.method).toBe("POST");
    expect(init.headers["X-Task-Actor"]).toBeTruthy();
    expect(init.headers["X-Task-Role"]).toBeTruthy();
    const body = JSON.parse(init.body) as { answer: string };
    expect(body.answer).toBe("Use the test environment.");
  });
});

describe("Step 66C.2 -- workroom security guardrails", () => {
  const pageSrc = readFileSync(
    join(__dirname, "..", "pages", "TaskWorkroom.tsx"),
    "utf-8",
  );
  const clientSrc = readFileSync(join(__dirname, "..", "tasks", "workroomClient.ts"), "utf-8");
  const typesSrc = readFileSync(join(__dirname, "..", "tasks", "workroomTypes.ts"), "utf-8");
  const allSrc = [pageSrc, clientSrc, typesSrc].join("\n");

  it("never uses dangerouslySetInnerHTML in the workroom page or client", () => {
    expect(allSrc.includes("dangerouslySetInnerHTML")).toBe(false);
  });

  it("workroom client sends X-Task-Actor and X-Task-Role on every call", () => {
    expect(clientSrc.includes("X-Task-Actor")).toBe(true);
    expect(clientSrc.includes("X-Task-Role")).toBe(true);
  });

  it("workroom client never touches a token / credential / csrf / cookie value", () => {
    for (const forbidden of ["token", "credential", "csrf", "cookie"]) {
      expect(clientSrc.toLowerCase().includes(forbidden)).toBe(false);
    }
  });

  it("workroom client exposes no generic request(method,url) helper", () => {
    expect(/export\s+(async\s+)?function\s+request\s*\(/.test(clientSrc)).toBe(false);
  });

  it("workroom client does not call external integration endpoints", () => {
    for (const forbidden of [
      "github.com",
      "discord.com",
      "slack.com",
      "telegram.org",
      "anthropic.com",
      "openai.com",
    ]) {
      expect(clientSrc.toLowerCase().includes(forbidden)).toBe(false);
    }
  });
});
