import { describe, expect, it } from "vitest";

import { monthLabel, monthOf, parseMonth, shiftMonth } from "./month";

describe("month", () => {
  it("knows the month of a day", () => {
    expect(monthOf(new Date(2026, 10, 1))).toBe("2026-11");
    expect(monthOf("2026-10-30")).toBe("2026-10");
  });

  it("moves across year boundaries", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
  });

  it("shows a German label", () => {
    expect(monthLabel("2026-11")).toBe("November 2026");
  });

  it("accepts only year-dash-month", () => {
    expect(parseMonth("2026-03")).toBe("2026-03");
    expect(parseMonth("2026-13")).toBeNull();
    expect(parseMonth("März")).toBeNull();
    expect(parseMonth(null)).toBeNull();
  });
});
