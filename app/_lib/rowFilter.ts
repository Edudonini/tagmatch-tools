export function rowMatchesQuery(row: Record<string, unknown>, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (q === "") return true;
  return Object.values(row).some((v) => {
    if (v === null || v === undefined) return false;
    return String(v).toLowerCase().includes(q);
  });
}

export type RowTypeKey = "SV" | "INT" | "NON" | "other";

export function rowTypeKey(value: unknown): RowTypeKey {
  const v = String(value ?? "").toLowerCase();
  if (v === "screen_view") return "SV";
  if (v === "interaction") return "INT";
  if (v === "noninteraction") return "NON";
  return "other";
}
