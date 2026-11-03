import { describe, expect, it } from "vitest";

import { formatEuro, parseGermanAmount } from "./money";

describe("parseGermanAmount", () => {
  it("reads German amounts into cents", () => {
    expect(parseGermanAmount("-1.409,84")).toBe(-140984);
  });

  it("reads amounts without thousands separator or cents", () => {
    expect(parseGermanAmount("-20,3")).toBe(-2030);
    expect(parseGermanAmount("3000")).toBe(300000);
  });

  it("ignores currency signs and spaces", () => {
    expect(parseGermanAmount(" 1.234,50 € ")).toBe(123450);
  });

  it("rejects text that is no amount", () => {
    expect(() => parseGermanAmount("zwanzig")).toThrow(/zwanzig/);
  });
});

describe("formatEuro", () => {
  it("shows whole euros with German separators", () => {
    expect(formatEuro(-140984)).toBe("-1.410 €");
  });

  it("shows cents when asked", () => {
    expect(formatEuro(123450, { cents: true })).toBe("1.234,50 €");
  });
});
