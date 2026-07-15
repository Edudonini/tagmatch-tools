import { describe, expect, it } from "vitest";
import { isNavActive, NAV_ITEMS } from "./nav";

describe("isNavActive", () => {
  it("matches the exact path", () => {
    expect(isNavActive("/extract-map", "/extract-map")).toBe(true);
  });
  it("matches a nested path under the item", () => {
    expect(isNavActive("/extract-map/review", "/extract-map")).toBe(true);
  });
  it("does not match a different tool", () => {
    expect(isNavActive("/match", "/extract-map")).toBe(false);
  });
  it("does not treat a prefix collision as active", () => {
    expect(isNavActive("/extract-maps-other", "/extract-map")).toBe(false);
  });
  it("exposes the five tools in order", () => {
    expect(NAV_ITEMS.map((n) => n.href)).toEqual([
      "/extract-map",
      "/extract-logs",
      "/build-query",
      "/match",
      "/convert-5.0",
    ]);
  });
});
