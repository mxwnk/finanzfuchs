import { describe, expect, it } from "vitest";

import type { BudgetItem } from "./budget-items";
import type { AssignedTransaction } from "./overview";
import { buildReserve } from "./reserve";

function yearly(id: number, name: string, amountCents: number, extra: Partial<BudgetItem> = {}): BudgetItem {
  return { id, category: "Auto", name, amountCents, rhythm: "Jahr", validFrom: "2026-01", validUntil: null, ...extra };
}

function payment(budgetItemId: number, amountCents: number, bookingDate: string): AssignedTransaction {
  return { id: `${budgetItemId}-${bookingDate}`, bookingDate, amountCents, counterparty: "X", purpose: "", category: "Auto", budgetItemId };
}

const INSURANCE = yearly(1, "KFZ-Versicherung", 36000);
const TAX = yearly(2, "KFZ-Steuer", 12000);
const FUEL: BudgetItem = { ...yearly(3, "Sprit", 5000), rhythm: "Monat" };

describe("buildReserve", () => {
  it("saves a twelfth of every yearly item per month up to the chosen one", () => {
    const reserve = buildReserve([INSURANCE, TAX, FUEL], [], "2026-03");

    expect(reserve.savedCents).toBe(3 * (3000 + 1000));
    expect(reserve.yearEndSavedCents).toBe(48000);
  });

  it("pays yearly costs from the reserve", () => {
    const reserve = buildReserve([INSURANCE, TAX], [payment(1, -36500, "2026-01-05")], "2026-03");

    expect(reserve.paidCents).toBe(36500);
    expect(reserve.balanceCents).toBe(12000 - 36500);
  });

  it("shows which yearly items are paid and which are still to come", () => {
    const reserve = buildReserve([INSURANCE, TAX], [payment(1, -36500, "2026-01-05")], "2026-03");

    expect(reserve.items).toEqual([
      { item: INSURANCE, paidCents: 36500, isPaid: true },
      { item: TAX, paidCents: 0, isPaid: false },
    ]);
    expect(reserve.openCents).toBe(12000);
  });

  it("only counts payments of the chosen year up to the chosen month", () => {
    const reserve = buildReserve(
      [INSURANCE],
      [payment(1, -36000, "2025-12-30"), payment(1, -100, "2026-04-01")],
      "2026-03",
    );

    expect(reserve.paidCents).toBe(0);
  });

  it("saves only for the months an item is valid", () => {
    const fromJuly = yearly(4, "Neu", 12000, { validFrom: "2026-07" });

    expect(buildReserve([fromJuly], [], "2026-08").savedCents).toBe(2000);
  });
});
