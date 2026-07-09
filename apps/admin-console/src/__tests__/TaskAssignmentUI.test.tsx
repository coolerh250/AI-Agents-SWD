import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { TaskList } from "../pages/TaskList";
import { TaskNew } from "../pages/TaskNew";
import { TaskDetail } from "../pages/TaskDetail";
import { NAV_ITEMS } from "../components/Nav";

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
  status: "draft",
  created_by: "test-operator",
  owner: "test-operator",
  project_id: null,
  environment: "test",
  production_effect: false,
  requires_approval: false,
  clarification_status: "none",
  delivery_status: "none",
  intake_planning_only: false,
  correlation_id: "22222222-2222-2222-2222-222222222222",
  metadata: {},
  created_at: "2026-07-09T00:00:00Z",
  updated_at: "2026-07-09T00:00:00Z",
};

function mockFetchOnce(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });
}

function renderWithRouter(initialEntries: string[] = ["/tasks"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/tasks" element={<TaskList />} />
        <Route path="/tasks/new" element={<TaskNew />} />
        <Route path="/tasks/:taskId" element={<TaskDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("TaskList", () => {
  it("renders tasks from GET /tasks with X-Task-Actor/X-Task-Role headers", async () => {
    const fetchMock = mockFetchOnce({ tasks: [SAMPLE_TASK], count: 1 });
    vi.stubGlobal("fetch", fetchMock);
    renderWithRouter();
    await waitFor(() => expect(screen.getByText("Sample task")).toBeDefined());
    const init = fetchMock.mock.calls[0][1] as { method: string; headers: Record<string, string> };
    expect(init.method).toBe("GET");
    expect(init.headers["X-Task-Actor"]).toBeTruthy();
    expect(init.headers["X-Task-Role"]).toBeTruthy();
  });

  it("shows empty state when there are no tasks", async () => {
    vi.stubGlobal("fetch", mockFetchOnce({ tasks: [], count: 0 }));
    renderWithRouter();
    await waitFor(() => expect(screen.getByText("No tasks yet")).toBeDefined());
  });

  it("shows an error state on server error", async () => {
    vi.stubGlobal("fetch", mockFetchOnce({ detail: "role_cannot_view_tasks" }, 403));
    renderWithRouter();
    await waitFor(() => expect(screen.getByText(/Unable to load data/)).toBeDefined());
  });

  it("shows the test role simulation banner", async () => {
    vi.stubGlobal("fetch", mockFetchOnce({ tasks: [], count: 0 }));
    renderWithRouter();
    await waitFor(() => expect(screen.getByTestId("test-role-banner")).toBeDefined());
    expect(screen.getByText(/Test role simulation active/)).toBeDefined();
  });

  it("links to the create-task page", async () => {
    vi.stubGlobal("fetch", mockFetchOnce({ tasks: [], count: 0 }));
    renderWithRouter();
    await waitFor(() => expect(screen.getByText("+ Create task")).toBeDefined());
  });
});

describe("TaskNew", () => {
  it("renders the create form", () => {
    renderWithRouter(["/tasks/new"]);
    expect(screen.getByText("Create Task")).toBeDefined();
  });

  it("requires a title before submitting", async () => {
    renderWithRouter(["/tasks/new"]);
    fireEvent.click(screen.getByText("Create Draft"));
    await waitFor(() => expect(screen.getByTestId("field-error")).toBeDefined());
  });

  it("shows the production_effect safety warning when checked", () => {
    renderWithRouter(["/tasks/new"]);
    const checkbox = screen.getByLabelText(/production_effect/i) as HTMLInputElement;
    fireEvent.click(checkbox);
    expect(screen.getByTestId("production-effect-warning")).toBeDefined();
    expect(screen.getByText(/will NOT execute/)).toBeDefined();
  });

  it("posts to /tasks with the required headers on Create Draft", async () => {
    const fetchMock = mockFetchOnce({ ...SAMPLE_TASK, dispatch_enabled: false });
    vi.stubGlobal("fetch", fetchMock);
    renderWithRouter(["/tasks/new"]);
    fireEvent.change(screen.getByLabelText(/^Title/), { target: { value: "New task" } });
    fireEvent.click(screen.getByText("Create Draft"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as [
      string,
      { method: string; headers: Record<string, string>; body: string },
    ];
    expect(String(url)).toContain("/tasks");
    expect(init.method).toBe("POST");
    expect(init.headers["X-Task-Actor"]).toBeTruthy();
    expect(init.headers["X-Task-Role"]).toBeTruthy();
    const body = JSON.parse(init.body) as { title: string; initial_status: string };
    expect(body.title).toBe("New task");
    expect(body.initial_status).toBe("draft");
  });
});

describe("TaskDetail", () => {
  it("renders task detail and dispatch_enabled=false", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(SAMPLE_TASK));
    renderWithRouter(["/tasks/11111111-1111-1111-1111-111111111111"]);
    await waitFor(() => expect(screen.getByTestId("dispatch-enabled-note")).toBeDefined());
    expect(screen.getByTestId("dispatch-enabled-note").textContent).toMatch(
      /no workflow dispatch occurs/i,
    );
  });

  it("shows Submit Draft button when status is draft", async () => {
    vi.stubGlobal("fetch", mockFetchOnce(SAMPLE_TASK));
    renderWithRouter(["/tasks/11111111-1111-1111-1111-111111111111"]);
    await waitFor(() => expect(screen.getByTestId("submit-draft")).toBeDefined());
  });

  it("calls POST /tasks/{id}/submit when Submit Draft is clicked", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => SAMPLE_TASK })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ ...SAMPLE_TASK, status: "intake_review", dispatch_enabled: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ ...SAMPLE_TASK, status: "intake_review" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    renderWithRouter(["/tasks/11111111-1111-1111-1111-111111111111"]);
    await waitFor(() => expect(screen.getByTestId("submit-draft")).toBeDefined());
    fireEvent.click(screen.getByTestId("submit-draft"));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
    const submitCall = fetchMock.mock.calls[1] as [string, { method: string }];
    expect(String(submitCall[0])).toContain("/submit");
    expect(submitCall[1].method).toBe("POST");
  });
});

describe("Tasks in navigation", () => {
  it("exposes /tasks in NAV_ITEMS", () => {
    expect(NAV_ITEMS.map((i) => i.to)).toContain("/tasks");
  });
});
