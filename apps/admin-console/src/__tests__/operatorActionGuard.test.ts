import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

// Stage 52 -- stricter guard for the v1 operator-action module. The module MAY
// issue mutating calls, but ONLY through explicit, named, typed methods. It must
// NOT expose a generic request(method,url,body), must send CSRF + credentials on
// mutations, and must never read/write the session token in localStorage.
const OPERATOR = join(__dirname, "..", "operator");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(ts|tsx)$/.test(name)) out.push(p);
  }
  return out;
}

describe("operator-action guard", () => {
  const sources = walk(OPERATOR)
    .map((f) => readFileSync(f, "utf-8"))
    .join("\n");
  const client = readFileSync(join(OPERATOR, "actionClient.ts"), "utf-8");

  it("exposes no generic request(method,url) helper", () => {
    expect(/export\s+(async\s+)?function\s+request\s*\(/.test(sources)).toBe(false);
    expect(/request\s*\(\s*method/i.test(sources)).toBe(false);
  });

  it("sends CSRF header on mutations", () => {
    expect(client.includes("X-CSRF-Token")).toBe(true);
  });

  it("includes credentials for the session cookie", () => {
    expect(client.includes('credentials: "same-origin"')).toBe(true);
  });

  it("sends an Idempotency-Key on mutations", () => {
    expect(client.includes("Idempotency-Key")).toBe(true);
  });

  it("never stores the session token in localStorage / sessionStorage", () => {
    expect(/localStorage|sessionStorage/.test(sources)).toBe(false);
  });

  it("does not enable any disabled high-risk action", () => {
    for (const forbidden of ["/deploy", "/github", "create_pr", "merge_pr", "execute-command"]) {
      expect(sources.includes(forbidden)).toBe(false);
    }
  });
});
