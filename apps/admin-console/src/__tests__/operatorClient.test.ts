import { describe, it, expect, vi, beforeEach } from "vitest";
import { operatorActions } from "../operator/actionClient";

// Capture fetch calls to assert CSRF header, credentials, idempotency, and that
// only explicit named methods issue requests (no generic verb/url helper).
let calls: { url: string; init: RequestInit }[] = [];

beforeEach(() => {
  calls = [];
  vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return Promise.resolve({
      json: () => Promise.resolve({ csrf_token: "t.sig", status: "ok", authenticated: true }),
    } as Response);
  });
});

describe("operator action client", () => {
  it("login then mutations send CSRF header + credentials + idempotency key", async () => {
    await operatorActions.testLogin("operator");
    await operatorActions.accept("pkg-1", "ok");
    const accept = calls.find((c) => c.url.includes("/operator-review/accept"));
    expect(accept).toBeTruthy();
    const headers = accept!.init.headers as Record<string, string>;
    expect(headers["X-CSRF-Token"]).toBe("t.sig");
    expect(headers["Idempotency-Key"]).toBeTruthy();
    expect(accept!.init.credentials).toBe("same-origin");
    expect(accept!.init.method).toBe("POST");
  });

  it("never writes auth token to localStorage", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem");
    void operatorActions.session();
    expect(spy).not.toHaveBeenCalled();
  });

  it("exposes only explicit named methods (no generic request)", () => {
    expect((operatorActions as unknown as { request?: unknown }).request).toBeUndefined();
    expect(typeof operatorActions.accept).toBe("function");
    expect(typeof operatorActions.reject).toBe("function");
    expect(typeof operatorActions.requestChanges).toBe("function");
    expect(typeof operatorActions.addNote).toBe("function");
    expect(typeof operatorActions.rerunVerification).toBe("function");
  });
});
