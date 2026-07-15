import { describe, expect, it } from "vitest";
import { rowMatchesQuery, rowTypeKey } from "./rowFilter";

describe("rowMatchesQuery", () => {
  const row = { sn: "/app/home", name: "screen_view", ct: "b2c_ecare" };
  it("matches case-insensitively across any value", () => {
    expect(rowMatchesQuery(row, "HOME")).toBe(true);
    expect(rowMatchesQuery(row, "ecare")).toBe(true);
  });
  it("returns true for an empty query", () => {
    expect(rowMatchesQuery(row, "")).toBe(true);
  });
  it("returns false when nothing matches", () => {
    expect(rowMatchesQuery(row, "zzz")).toBe(false);
  });
});

describe("rowTypeKey", () => {
  it("buckets the known event types", () => {
    expect(rowTypeKey("screen_view")).toBe("SV");
    expect(rowTypeKey("interaction")).toBe("INT");
    expect(rowTypeKey("noninteraction")).toBe("NON");
  });
  it("buckets anything else as other", () => {
    expect(rowTypeKey("click")).toBe("other");
    expect(rowTypeKey(null)).toBe("other");
  });
});
