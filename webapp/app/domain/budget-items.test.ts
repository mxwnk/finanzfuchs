import { describe, expect, it } from "vitest";

import { type BudgetItem, monthlyBudgets, validItems, yearlyItems } from "./budget-items";

function item(name: string, category: BudgetItem["category"], amountCents: number, rhythm: BudgetItem["rhythm"], extra: Partial<BudgetItem> = {}): BudgetItem {
  return { id: name.length, category, name, amountCents, rhythm, validFrom: "2026-01", validUntil: null, ...extra };
}

const FUEL = item("Sprit", "Auto", 5000, "Monat");
const CHARGING = item("Strom", "Auto", 15000, "Monat", { validFrom: "2026-08" });
const INSURANCE = item("KFZ-Versicherung", "Auto", 38618, "Jahr");
const FOOD = item("Lebensmittel", "Täglicher Bedarf", 80000, "Monat");

describe("validItems", () => {
  it("keeps items whose validity covers the month", () => {
    expect(validItems([FUEL, CHARGING], "2026-07")).toEqual([FUEL]);
    expect(validItems([FUEL, CHARGING], "2026-08")).toEqual([FUEL, CHARGING]);
  });

  it("drops items that ended before the month", () => {
    const ended = item("Alt", "Auto", 100, "Monat", { validUntil: "2026-06" });

    expect(validItems([ended], "2026-07")).toEqual([]);
    expect(validItems([ended], "2026-06")).toEqual([ended]);
  });
});

describe("monthlyBudgets", () => {
  it("adds the monthly items of each category", () => {
    expect(monthlyBudgets([FUEL, CHARGING, FOOD], "2026-08")).toEqual({ Auto: 20000, "Täglicher Bedarf": 80000 });
  });

  it("leaves yearly items out of the month", () => {
    expect(monthlyBudgets([FUEL, INSURANCE], "2026-08")).toEqual({ Auto: 5000 });
  });
});

describe("yearlyItems", () => {
  it("lists the yearly items valid in the month", () => {
    expect(yearlyItems([FUEL, INSURANCE, FOOD], "2026-08")).toEqual([INSURANCE]);
  });
});
