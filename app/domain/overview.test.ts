import { describe, expect, it } from "vitest";

import { IGNORED } from "./categories";
import { buildMonthOverview, type AssignedTransaction } from "./overview";

function booking(amountCents: number, category: AssignedTransaction["category"], bookingDate = "2026-11-05"): AssignedTransaction {
  return { id: `${bookingDate}-${amountCents}-${category}`, bookingDate, amountCents, counterparty: "X", purpose: "", category, budgetItemId: null };
}

const BUDGETS = { "Täglicher Bedarf": 80000, Wohnen: 200000 };

describe("buildMonthOverview", () => {
  it("compares spending per category with its budget", () => {
    const overview = buildMonthOverview("2026-11", BUDGETS, [booking(-30000, "Täglicher Bedarf")]);

    const daily = overview.categories.find((row) => row.category === "Täglicher Bedarf");
    expect(daily).toMatchObject({ budgetCents: 80000, spentCents: 30000, remainingCents: 50000 });
  });

  it("lists every category, also those without budget or spending", () => {
    const overview = buildMonthOverview("2026-11", {}, []);

    expect(overview.categories).toHaveLength(8);
    expect(overview.categories[0]).toMatchObject({ category: "Wohnen", budgetCents: 0, spentCents: 0 });
  });

  it("lets refunds reduce what a category spent", () => {
    const overview = buildMonthOverview("2026-11", BUDGETS, [
      booking(-10000, "Täglicher Bedarf"),
      booking(2000, "Täglicher Bedarf"),
    ]);

    expect(overview.categories.find((row) => row.category === "Täglicher Bedarf")?.spentCents).toBe(8000);
  });

  it("counts unassigned spending separately and never ignored transfers", () => {
    const overview = buildMonthOverview("2026-11", BUDGETS, [
      booking(-5000, null),
      booking(-45000, IGNORED),
      booking(300000, null),
    ]);

    expect(overview.unassignedCount).toBe(1);
    expect(overview.unassignedCents).toBe(5000);
    expect(overview.totalSpentCents).toBe(5000);
  });

  it("adds budgets and spending up", () => {
    const overview = buildMonthOverview("2026-11", BUDGETS, [booking(-30000, "Täglicher Bedarf"), booking(-200000, "Wohnen")]);

    expect(overview.totalBudgetCents).toBe(280000);
    expect(overview.totalSpentCents).toBe(230000);
  });

  it("only looks at the chosen month", () => {
    const overview = buildMonthOverview("2026-11", BUDGETS, [booking(-30000, "Wohnen", "2026-10-31")]);

    expect(overview.totalSpentCents).toBe(0);
    expect(overview.transactionCount).toBe(0);
  });

  it("leaves payments of yearly items to the reserve", () => {
    const yearlyPayment = { ...booking(-38600, "Wohnen"), budgetItemId: 7 };

    const overview = buildMonthOverview("2026-11", BUDGETS, [yearlyPayment]);

    expect(overview.totalSpentCents).toBe(0);
  });
});
