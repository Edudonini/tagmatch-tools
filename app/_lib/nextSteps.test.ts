import { describe, expect, it } from "vitest";
import { nextStepsFor } from "./nextSteps";

describe("nextStepsFor", () => {
  it("offers query, matching, and convert after a map extraction", () => {
    const steps = nextStepsFor("extract-map", true, true);
    expect(steps.map((s) => s.href)).toEqual(["/build-query", "/match", "/convert-5.0"]);
  });
  it("hints to extract logs when matching has no logs yet", () => {
    const steps = nextStepsFor("extract-map", true, false);
    const match = steps.find((s) => s.href === "/match");
    expect(match?.hint).toContain("logs");
    expect(match?.hintHref).toBe("/extract-logs");
  });
  it("has no logs hint on matching once logs exist", () => {
    const steps = nextStepsFor("extract-map", true, true);
    const match = steps.find((s) => s.href === "/match");
    expect(match?.hint).toBeUndefined();
  });
  it("offers only matching after a log extraction, hinting for a map", () => {
    const steps = nextStepsFor("extract-logs", false, true);
    expect(steps.map((s) => s.href)).toEqual(["/match"]);
    expect(steps[0].hint).toContain("mapa");
    expect(steps[0].hintHref).toBe("/extract-map");
  });
  it("drops the map hint on matching once a map exists", () => {
    const steps = nextStepsFor("extract-logs", true, true);
    expect(steps[0].hint).toBeUndefined();
  });
});
