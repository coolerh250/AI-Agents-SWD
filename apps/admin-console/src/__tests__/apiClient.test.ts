import { describe, it, expect, vi, afterEach } from "vitest";
import { apiGet, ApiError, SUPPORTED_METHODS } from "../api/client";

afterEach(() => vi.restoreAllMocks());

describe("apiClient", () => {
  it("issues GET requests only", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ hello: "world" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const out = await apiGet<{ hello: string }>("/operations/admin-console/overview");
    expect(out.hello).toBe("world");
    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("GET");
    expect(SUPPORTED_METHODS).toEqual(["GET"]);
  });

  it("maps 404 to ApiError code 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }),
    );
    await expect(apiGet("/missing")).rejects.toMatchObject({ code: 404 });
  });

  it("throws ApiError on non-ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }),
    );
    await expect(apiGet("/x")).rejects.toBeInstanceOf(ApiError);
  });
});
