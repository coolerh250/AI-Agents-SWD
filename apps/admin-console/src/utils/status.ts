// Stage 50 -- map status strings to a semantic tone for badges.

export type Tone = "ok" | "warn" | "bad" | "neutral";

export function statusTone(value: unknown): Tone {
  const t = String(value == null ? "" : value).toLowerCase();
  if (!t) return "neutral";
  if (/(failed|blocked|unsafe|error|rejected)/.test(t)) return "bad";
  if (/(ready_for_review|ready_for_operator_review)/.test(t)) return "ok";
  if (/(pending|passed_with_findings|warning|with_documented_gaps|needs_changes|draft)/.test(t))
    return "warn";
  if (/(passed|safe|completed|ok|true)/.test(t)) return "ok";
  return "neutral";
}
