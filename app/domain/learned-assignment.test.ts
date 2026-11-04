import { describe, expect, it } from "vitest";

import { IGNORED } from "./categories";
import { learnAssignments } from "./learned-assignment";
import type { AssignedTransaction } from "./overview";

function payment(
  id: string,
  counterparty: string,
  amountCents: number,
  category: AssignedTransaction["category"] = null,
  { bookingDate = "2026-10-05", budgetItemId = null }: { bookingDate?: string; budgetItemId?: number | null } = {},
): AssignedTransaction {
  return { id, bookingDate, amountCents, counterparty, purpose: "", category, budgetItemId };
}

describe("learnAssignments", () => {
  it("takes the category last chosen for the same counterparty and amount", () => {
    const history = [
      payment("older", "Sportverein", -4000, "Sparen", { bookingDate: "2026-08-01" }),
      payment("newer", "Sportverein", -4000, "Freizeit", { bookingDate: "2026-10-01" }),
    ];

    const learned = learnAssignments([payment("open", "Sportverein", -4000)], history);

    expect(learned).toEqual([{ transactionId: "open", category: "Freizeit", budgetItemId: null }]);
  });

  it("tells payments to the same counterparty apart by their amount", () => {
    const history = [
      payment("a", "Partnerkonto", -5000, "Sparen"),
      payment("b", "Partnerkonto", -20000, "Freizeit"),
      payment("c", "Partnerkonto", -20000, "Freizeit"),
    ];

    const learned = learnAssignments([payment("small", "Partnerkonto", -5000), payment("large", "Partnerkonto", -20000)], history);

    expect(learned.map((assignment) => assignment.category)).toEqual(["Sparen", "Freizeit"]);
  });

  it("keeps the yearly item of an earlier payment with the same amount", () => {
    const history = [payment("last-year", "Versicherer", -38618, "Versicherungen", { budgetItemId: 7 })];

    const [learned] = learnAssignments([payment("open", "Versicherer", -38618)], history);

    expect(learned).toEqual({ transactionId: "open", category: "Versicherungen", budgetItemId: 7 });
  });

  it("takes the usual category of a counterparty when the amount is new", () => {
    const history = [
      payment("a", "Supermarkt", -2030, "Täglicher Bedarf"),
      payment("b", "Supermarkt", -4512, "Täglicher Bedarf"),
      payment("c", "Supermarkt", -899, "Täglicher Bedarf"),
      payment("d", "Supermarkt", -1250, "Täglicher Bedarf"),
      payment("e", "Supermarkt", -6000, "Freizeit"),
    ];

    const learned = learnAssignments([payment("open", "Supermarkt", -1777)], history);

    expect(learned).toEqual([{ transactionId: "open", category: "Täglicher Bedarf", budgetItemId: null }]);
  });

  it("never brings a yearly item along for a new amount", () => {
    const history = [
      payment("a", "Versicherer", -38618, "Versicherungen", { budgetItemId: 7 }),
      payment("b", "Versicherer", -39000, "Versicherungen", { budgetItemId: 7 }),
    ];

    const [learned] = learnAssignments([payment("open", "Versicherer", -41000)], history);

    expect(learned.budgetItemId).toBeNull();
  });

  it("leaves a payment open when its counterparty went to different categories", () => {
    const history = [
      payment("a", "Bezahldienst", -1000, "Fixkosten"),
      payment("b", "Bezahldienst", -2000, "Auto"),
      payment("c", "Bezahldienst", -3000, "Freizeit"),
    ];

    expect(learnAssignments([payment("open", "Bezahldienst", -1500)], history)).toEqual([]);
  });

  it("does not trust a single earlier payment with another amount", () => {
    const history = [payment("a", "Laden", -1000, "Freizeit")];

    expect(learnAssignments([payment("open", "Laden", -2500)], history)).toEqual([]);
  });

  it("leaves a payment open when its counterparty is unknown", () => {
    const history = [payment("a", "Supermarkt", -2030, "Täglicher Bedarf")];

    expect(learnAssignments([payment("open", "Baumarkt", -2030)], history)).toEqual([]);
  });

  it("learns nothing from payments without a counterparty", () => {
    const history = [payment("a", "", -2030, "Täglicher Bedarf"), payment("b", " ", -2030, "Täglicher Bedarf")];

    expect(learnAssignments([payment("open", "", -2030)], history)).toEqual([]);
  });

  it("matches a counterparty regardless of case and surrounding spaces", () => {
    const history = [payment("a", "SUPERMARKT", -2030, "Täglicher Bedarf")];

    const learned = learnAssignments([payment("open", " Supermarkt ", -2030)], history);

    expect(learned.map((assignment) => assignment.category)).toEqual(["Täglicher Bedarf"]);
  });

  it("learns transfers between own accounts as no spending", () => {
    const history = [payment("a", "Eigenes Konto", -45000, IGNORED)];

    const learned = learnAssignments([payment("open", "Eigenes Konto", -45000)], history);

    expect(learned.map((assignment) => assignment.category)).toEqual([IGNORED]);
  });

  it("learns only from payments that already have a category", () => {
    const history = [payment("a", "Supermarkt", -2030, null)];

    expect(learnAssignments([payment("open", "Supermarkt", -2030)], history)).toEqual([]);
  });
});
