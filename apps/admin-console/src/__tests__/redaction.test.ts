import { describe, it, expect } from "vitest";
import { redact, isSecretKey, isForbiddenKey } from "../utils/safety";

describe("redaction", () => {
  it("redacts secret-like keys", () => {
    const out = redact({
      token: "ghp_secret",
      api_key: "sk-123",
      password: "pw",
      hmac_key: "k",
      private_key: "p",
      webhook_url: "https://x",
      status: "passed",
    });
    expect(out.token).toBe("***REDACTED***");
    expect(out.api_key).toBe("***REDACTED***");
    expect(out.password).toBe("***REDACTED***");
    expect(out.hmac_key).toBe("***REDACTED***");
    expect(out.private_key).toBe("***REDACTED***");
    expect(out.webhook_url).toBe("***REDACTED***");
    expect(out.status).toBe("passed");
  });

  it("drops chain-of-thought / raw prompt / transcript keys", () => {
    const out = redact({ chain_of_thought: "x", raw_prompt: "y", transcript: "z", ok: 1 });
    expect("chain_of_thought" in out).toBe(false);
    expect("raw_prompt" in out).toBe(false);
    expect("transcript" in out).toBe(false);
    expect(out.ok).toBe(1);
  });

  it("redacts nested structures", () => {
    const out = redact({ a: { b: { token: "t", v: 2 } }, list: [{ secret: "s" }] });
    expect((out.a as any).b.token).toBe("***REDACTED***");
    expect((out.list as any)[0].secret).toBe("***REDACTED***");
  });

  it("classifies keys", () => {
    expect(isSecretKey("API_KEY")).toBe(true);
    expect(isSecretKey("status")).toBe(false);
    expect(isForbiddenKey("chain_of_thought_persisted")).toBe(true);
  });
});
