import { describe, it, expect } from "vitest";
import { statusTone } from "../utils/status";
import { display, titleCase } from "../utils/format";

describe("status formatting", () => {
  it("maps statuses to tones", () => {
    expect(statusTone("passed")).toBe("ok");
    expect(statusTone("ready_for_operator_review")).toBe("ok");
    expect(statusTone("passed_with_findings")).toBe("warn");
    expect(statusTone("pending")).toBe("warn");
    expect(statusTone("failed")).toBe("bad");
    expect(statusTone("blocked")).toBe("bad");
    expect(statusTone("")).toBe("neutral");
  });

  it("displays values", () => {
    expect(display(null)).toBe("—");
    expect(display(true)).toBe("true");
    expect(display(["a", "b"])).toBe("a, b");
    expect(display([])).toBe("none");
    expect(display(3)).toBe("3");
  });

  it("title-cases keys", () => {
    expect(titleCase("latest_human_acceptance_status")).toBe("Latest Human Acceptance Status");
  });
});
