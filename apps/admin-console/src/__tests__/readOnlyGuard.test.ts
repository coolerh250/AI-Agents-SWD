import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

// Read-only guard: scan the Admin Console v0 read-only surface and assert it
// never performs a mutating HTTP call or an operator action. The Stage 52 v1
// operator-action surface lives under ``src/operator/`` (a clearly delineated,
// audited module) and is excluded here -- it is covered by the STRICTER
// operatorActionGuard test instead. Everything else (all read-only views) must
// remain write-free, so this invariant is unchanged for v0.
//
// Step 66B.2 adds a second write-capable module, ``src/tasks/`` (the task
// assignment API client + test-role simulation), likewise excluded here and
// covered by its own stricter taskApiGuard test instead.
const SRC = join(__dirname, "..");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      if (name === "__tests__" || name === "operator" || name === "tasks") continue;
      out.push(...walk(p));
    } else if (/\.(ts|tsx)$/.test(name)) {
      // OperatorConsole composes the operator module; skip the page shell only.
      if (name === "OperatorConsole.tsx") continue;
      out.push(p);
    }
  }
  return out;
}

describe("read-only guard", () => {
  const files = walk(SRC);
  const sources = files.map((f) => readFileSync(f, "utf-8")).join("\n");

  it("uses no mutating fetch methods", () => {
    expect(/method:\s*["'](POST|PUT|PATCH|DELETE)["']/i.test(sources)).toBe(false);
  });

  it("calls no operator action endpoints", () => {
    for (const forbidden of [
      "/operator-review/accept",
      "/operator-review/reject",
      "/operator-review/request-changes",
      "/delivery-package/build",
      "/mini-delivery-pilots/run",
      "/workflow/resume",
      "/approve",
      "/deploy",
    ]) {
      expect(sources.includes(forbidden)).toBe(false);
    }
  });

  it("does not write sensitive data to localStorage", () => {
    expect(/localStorage\.setItem/.test(sources)).toBe(false);
  });
});
