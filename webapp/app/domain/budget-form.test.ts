import { describe, expect, it } from "vitest";

import { readBudgetForm } from "./budget-form";

function form(entries: [string, string][]): FormData {
  const data = new FormData();
  for (const [key, value] of entries) data.append(key, value);
  return data;
}

describe("readBudgetForm", () => {
  it("reads changed items by their id", () => {
    const result = readBudgetForm(form([
      ["item", "7"], ["category-7", "Auto"], ["name-7", "Sprit"], ["amount-7", "50"], ["rhythm-7", "Monat"],
    ]), "2026-11");

    expect(result.errors).toEqual({});
    expect(result.changed).toEqual([{ id: 7, category: "Auto", name: "Sprit", amountCents: 5000, rhythm: "Monat" }]);
  });

  it("collects items marked for removal", () => {
    const result = readBudgetForm(form([
      ["item", "7"], ["category-7", "Auto"], ["name-7", "Sprit"], ["amount-7", "50"], ["rhythm-7", "Monat"], ["remove-7", "on"],
    ]), "2026-11");

    expect(result.removed).toEqual([7]);
    expect(result.changed).toEqual([]);
  });

  it("adds a new item when its name is filled in, valid from the month shown", () => {
    const result = readBudgetForm(form([
      ["new", "Auto"], ["new-name-Auto", "KFZ-Versicherung"], ["new-amount-Auto", "386,18"], ["new-rhythm-Auto", "Jahr"],
      ["new", "Wohnen"], ["new-name-Wohnen", ""], ["new-amount-Wohnen", ""], ["new-rhythm-Wohnen", "Monat"],
    ]), "2026-11");

    expect(result.added).toEqual([
      { category: "Auto", name: "KFZ-Versicherung", amountCents: 38618, rhythm: "Jahr", validFrom: "2026-11", validUntil: null },
    ]);
  });

  it("explains a broken amount next to its item", () => {
    const result = readBudgetForm(form([
      ["item", "7"], ["category-7", "Auto"], ["name-7", "Sprit"], ["amount-7", "viel"], ["rhythm-7", "Monat"],
    ]), "2026-11");

    expect(result.errors["7"]).toMatch(/viel/);
  });

  it("needs a name for every item", () => {
    const result = readBudgetForm(form([
      ["item", "7"], ["category-7", "Auto"], ["name-7", " "], ["amount-7", "50"], ["rhythm-7", "Monat"],
    ]), "2026-11");

    expect(result.errors["7"]).toMatch(/Name/);
  });
});
