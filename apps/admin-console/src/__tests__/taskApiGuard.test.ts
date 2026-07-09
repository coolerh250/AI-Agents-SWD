import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

// Step 66B.2 -- stricter guard for the task-assignment write module. Unlike
// src/operator/ (real session cookie + CSRF), this module has NO real identity
// model yet -- it is a documented, fail-closed TEST-ONLY role simulation (see
// docs/test/step66b2-task-assignment-ui-safety-record.md). It may persist a
// non-secret {actor, role} label to localStorage for that simulation only. It
// must: expose only named task methods (no generic request(method,url)); send
// X-Task-Actor + X-Task-Role on every call; target only /tasks endpoints; never
// touch a token/credential/csrf/cookie value; and never call an external
// integration or governed operator endpoint.
const TASKS = join(__dirname, "..", "tasks");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(ts|tsx)$/.test(name)) out.push(p);
  }
  return out;
}

describe("task-api guard", () => {
  const sources = walk(TASKS)
    .map((f) => readFileSync(f, "utf-8"))
    .join("\n");
  const client = readFileSync(join(TASKS, "taskClient.ts"), "utf-8");

  it("exposes no generic request(method,url) helper", () => {
    expect(/export\s+(async\s+)?function\s+request\s*\(/.test(sources)).toBe(false);
  });

  it("sends X-Task-Actor and X-Task-Role on every call", () => {
    expect(client.includes("X-Task-Actor")).toBe(true);
    expect(client.includes("X-Task-Role")).toBe(true);
  });

  it("only targets the /tasks API base", () => {
    expect(/API_BASE\s*\+\s*["']\/tasks["']/.test(client)).toBe(true);
  });

  it("never touches a token / credential / csrf / cookie value", () => {
    for (const forbidden of ["token", "credential", "csrf", "cookie"]) {
      expect(sources.toLowerCase().includes(forbidden)).toBe(false);
    }
  });

  it("localStorage is only used for the non-secret test-role identity", () => {
    const calls = [...sources.matchAll(/localStorage\.setItem\(([^,]+),/g)].map((m) => m[1].trim());
    expect(calls.length).toBeGreaterThan(0);
    for (const key of calls) {
      expect(key.includes("STORAGE_KEY")).toBe(true);
    }
  });

  it("does not call external integration or governed operator endpoints", () => {
    for (const forbidden of [
      "/operator-review",
      "/deploy",
      "/approve",
      "github.com",
      "discord.com",
      "slack.com",
      "telegram.org",
      "anthropic.com",
      "openai.com",
    ]) {
      expect(sources.toLowerCase().includes(forbidden)).toBe(false);
    }
  });
});
