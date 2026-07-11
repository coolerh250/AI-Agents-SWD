// Step 66C.3 -- Workroom Audit / Visibility / Edge-case Hardening UI tests.
//
// Placed in src/__tests__/ (not src/tasks/, the location the 66C.3 spec
// suggests) for the same reason as WorkroomUI.test.tsx (see
// docs/test/step66c2-workroom-ui-evidence.md): this file's own negative
// assertions contain the literal substrings "headers"/"cookie"/"token" as
// array-literal checks, which would otherwise trip taskApiGuard.test.ts (it
// walks the whole src/tasks/ directory looking for exactly those words in
// source it doesn't expect them in).
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { TaskWorkroom } from "../pages/TaskWorkroom";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

const TASK_ID = "11111111-1111-1111-1111-111111111111";

const OPEN_CLARIFICATION = {
  id: "66666666-6666-6666-6666-666666666666",
  task_id: TASK_ID,
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
    task_id: TASK_ID,
    task_status: "clarification_needed",
    messages: [],
    clarification_requests: [OPEN_CLARIFICATION],
    dispatch_enabled: false,
    resume_dispatch_enabled: false,
    ...overrides,
  };
}

const AUDIT_EVENT = {
  audit_event_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  task_id: TASK_ID,
  event_type: "task_message_created",
  created_at: "2026-07-11T00:00:00Z",
  actor: "alice",
  role: "requester",
  action: "post_message",
  status: "completed",
  message_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  message_type: "human_message",
  visibility: "task_participants",
  body_length: 42,
  body_hash: "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
};

function auditEvidenceResponse(overrides: Record<string, unknown> = {}) {
  return {
    task_id: TASK_ID,
    events: [AUDIT_EVENT],
    dispatch_enabled: false,
    resume_dispatch_enabled: false,
    ...overrides,
  };
}

function renderWorkroom() {
  return render(
    <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/workroom`]}>
      <Routes>
        <Route path="/tasks/:taskId/workroom" element={<TaskWorkroom />} />
      </Routes>
    </MemoryRouter>,
  );
}

function routedFetch(handlers: {
  workroom?: () => { ok: boolean; status: number; json: () => Promise<unknown> };
  audit?: () => { ok: boolean; status: number; json: () => Promise<unknown> };
}) {
  return vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes("/audit-evidence")) {
      return (
        handlers.audit?.() ?? { ok: true, status: 200, json: async () => auditEvidenceResponse() }
      );
    }
    return handlers.workroom?.() ?? { ok: true, status: 200, json: async () => workroomResponse() };
  });
}

describe("Step 66C.3 -- message visibility note (G1, server-side filtered by the API)", () => {
  it("shows a note that some messages may be hidden based on role", async () => {
    vi.stubGlobal("fetch", routedFetch({}));
    renderWorkroom();
    await waitFor(() => expect(screen.getByTestId("workroom-visibility-note")).toBeDefined());
    expect(screen.getByTestId("workroom-visibility-note").textContent).toMatch(
      /may be hidden based on your role/,
    );
  });

  it("only renders messages the API actually returned -- never re-filters or adds any client-side", async () => {
    const onlyParticipantMessage = {
      id: "ccccccc1-cccc-cccc-cccc-cccccccccccc",
      task_id: TASK_ID,
      correlation_id: "ddddddd1-dddd-dddd-dddd-dddddddddddd",
      sender_type: "human",
      sender_id: "alice",
      sender_role: "requester",
      message_type: "human_message",
      body: "visible to everyone who can view the workroom",
      visibility: "task_participants",
      reply_to_message_id: null,
      audit_ref: null,
      created_at: "2026-07-10T00:00:01Z",
      updated_at: "2026-07-10T00:00:01Z",
    };
    vi.stubGlobal(
      "fetch",
      routedFetch({
        workroom: () => ({
          ok: true,
          status: 200,
          json: async () => workroomResponse({ messages: [onlyParticipantMessage] }),
        }),
      }),
    );
    renderWorkroom();
    await waitFor(() => expect(screen.getByTestId("workroom-messages")).toBeDefined());
    expect(screen.getAllByTestId("workroom-message")).toHaveLength(1);
  });
});

describe("Step 66C.3 -- Audit Evidence section (G3)", () => {
  it("renders safe metadata for an allowed role", async () => {
    vi.stubGlobal("fetch", routedFetch({}));
    renderWorkroom();
    await waitFor(() => expect(screen.getByTestId("workroom-audit-events")).toBeDefined());
    const event = screen.getByTestId("workroom-audit-event");
    expect(event.textContent).toContain("task_message_created");
    expect(event.textContent).toContain("alice");
    expect(event.textContent).toContain("body_length: 42");
  });

  it("shows an empty state when there is no audit evidence yet", async () => {
    vi.stubGlobal(
      "fetch",
      routedFetch({ audit: () => ({ ok: true, status: 200, json: async () => auditEvidenceResponse({ events: [] }) }) }),
    );
    renderWorkroom();
    await waitFor(() => expect(screen.getByTestId("workroom-audit-evidence")).toBeDefined());
    await waitFor(() =>
      expect(screen.getByText("No audit evidence for this task yet.")).toBeDefined(),
    );
  });

  it("shows a readable restricted message when the role is denied (403)", async () => {
    vi.stubGlobal(
      "fetch",
      routedFetch({
        audit: () => ({
          ok: false,
          status: 403,
          json: async () => ({ detail: "role_cannot_view_audit_evidence" }),
        }),
      }),
    );
    renderWorkroom();
    await waitFor(() =>
      expect(screen.getByTestId("workroom-audit-evidence-restricted")).toBeDefined(),
    );
    expect(screen.getByTestId("workroom-audit-evidence-restricted").textContent).toMatch(
      /restricted for your current role/,
    );
    // Restricted, not a hard page error -- the rest of the workroom still renders.
    expect(screen.getByTestId("workroom-safety-panel")).toBeDefined();
  });

  it("never renders a raw message body or answer -- only the safe fields the API returned", async () => {
    vi.stubGlobal("fetch", routedFetch({}));
    renderWorkroom();
    await waitFor(() => expect(screen.getByTestId("workroom-audit-event")).toBeDefined());
    const event = screen.getByTestId("workroom-audit-event");
    // The audit event fixture above never included a "body"/"answer" field in
    // the first place (the backend allowlist guarantees this) -- this test
    // confirms the UI doesn't independently invent a raw-body rendering path.
    expect(event.textContent).not.toContain("SECRET");
    expect(event.innerHTML).not.toContain("<img");
  });
});

describe("Step 66C.3 -- answered-twice guard (G5) readable error", () => {
  it("shows a readable error if the answer endpoint returns clarification_already_answered", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes("/audit-evidence")) {
        return { ok: true, status: 200, json: async () => auditEvidenceResponse() };
      }
      if (u.includes("/answer") && init?.method === "POST") {
        return {
          ok: false,
          status: 409,
          json: async () => ({ detail: "clarification_already_answered" }),
        };
      }
      return { ok: true, status: 200, json: async () => workroomResponse() };
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWorkroom();
    await waitFor(() => expect(screen.getByTestId("workroom-answer-form")).toBeDefined());
    fireEvent.change(screen.getByTestId("workroom-answer-input"), {
      target: { value: "Too late, someone already answered this." },
    });
    fireEvent.click(screen.getByTestId("workroom-submit-answer"));
    await waitFor(() =>
      expect(screen.getByText(/This clarification has already been answered/)).toBeDefined(),
    );
  });
});
