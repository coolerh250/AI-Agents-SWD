import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { TaskList } from "../pages/TaskList";

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}

function renderTaskList(entry: string) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ tasks: [], count: 0 }),
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <MemoryRouter initialEntries={[entry]}>
      <LocationProbe />
      <Routes>
        <Route path="/tasks" element={<TaskList />} />
      </Routes>
    </MemoryRouter>,
  );
  return fetchMock;
}

function requestedUrls(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return fetchMock.mock.calls.map(([input]) => String(input));
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("FE.1C.1 TaskList status deep links", () => {
  it.each(["blocked", "clarification_needed"])(
    "initializes the existing filter and request for status=%s",
    async (status) => {
      const fetchMock = renderTaskList(`/tasks?status=${status}`);

      const select = screen.getByLabelText("Status") as HTMLSelectElement;
      expect(select.value).toBe(status);
      await waitFor(() =>
        expect(requestedUrls(fetchMock).some((url) => url.includes(`status=${status}`))).toBe(true),
      );
    },
  );

  it.each(["unknown", "", "production_executed"])(
    "ignores invalid status=%s without sending it to the backend",
    async (status) => {
      const fetchMock = renderTaskList(`/tasks?status=${status}`);

      expect((screen.getByLabelText("Status") as HTMLSelectElement).value).toBe("");
      await waitFor(() => expect(fetchMock).toHaveBeenCalled());
      expect(requestedUrls(fetchMock).every((url) => !url.includes("status="))).toBe(true);
      expect(screen.getByTestId("location").textContent).toBe(`/tasks?status=${status}`);
    },
  );

  it("keeps manual filtering one-way and does not update the URL", async () => {
    const fetchMock = renderTaskList("/tasks?status=blocked");
    const select = screen.getByLabelText("Status") as HTMLSelectElement;
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    fireEvent.change(select, { target: { value: "failed" } });

    expect(select.value).toBe("failed");
    await waitFor(() =>
      expect(requestedUrls(fetchMock).some((url) => url.includes("status=failed"))).toBe(true),
    );
    expect(screen.getByTestId("location").textContent).toBe("/tasks?status=blocked");
  });
});
