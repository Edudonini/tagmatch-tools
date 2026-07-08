"use client";

export type SpecRow = Record<string, unknown>;

const HANDOFF_KEY = "tagmatch:spec-handoff";

export function storeSpecHandoff(rows: SpecRow[]): void {
  try {
    sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(rows));
  } catch {
    // sessionStorage unavailable/full — handoff silently unavailable.
  }
}

// Take semantics: returns the handed-off rows once, then clears the key so a
// refresh or re-navigation does not silently reload a stale spec.
export function takeSpecHandoff(): SpecRow[] | null {
  try {
    const raw = sessionStorage.getItem(HANDOFF_KEY);
    if (!raw) return null;
    sessionStorage.removeItem(HANDOFF_KEY);
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as SpecRow[]) : null;
  } catch {
    return null;
  }
}

export function rowsToSpecFile(rows: SpecRow[]): File {
  return new File([JSON.stringify(rows)], "spec.json", { type: "application/json" });
}
