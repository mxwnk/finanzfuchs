import { DatabaseSync } from "node:sqlite";

import { beforeEach, describe, expect, it } from "vitest";

import { IGNORED } from "~/domain/categories";
import type { BankTransaction } from "~/domain/dkb-export.server";

import {
  addBudgetItem,
  addTransactions,
  assignTransaction,
  budgetItems,
  deleteBudgetItem,
  type NewBudgetItem,
  openDatabase,
  transactionsInMonth,
  unassignedSpending,
  updateBudgetItem,
  yearlyPayments,
  type Database,
} from "./database";

function bankTransaction(id: string, bookingDate = "2026-11-05", amountCents = -2030): BankTransaction {
  return { id, account: "DE01", bookingDate, amountCents, counterparty: "REWE", purpose: "Einkauf" };
}

let database: Database;

beforeEach(() => {
  database = openDatabase(":memory:");
});

describe("transactions", () => {
  it("adds only transactions it does not know yet", () => {
    addTransactions(database, [bankTransaction("a")]);

    const added = addTransactions(database, [bankTransaction("a"), bankTransaction("b")]);

    expect(added).toBe(1);
    expect(transactionsInMonth(database, "2026-11")).toHaveLength(2);
  });

  it("returns a month's transactions newest first, unassigned at first", () => {
    addTransactions(database, [bankTransaction("old", "2026-11-01"), bankTransaction("new", "2026-11-20")]);

    const [newest, oldest] = transactionsInMonth(database, "2026-11");

    expect([newest.id, oldest.id]).toEqual(["new", "old"]);
    expect(newest.category).toBeNull();
  });

  it("lists unassigned spending but not income or assigned ones", () => {
    addTransactions(database, [bankTransaction("spent"), bankTransaction("income", "2026-11-01", 300000), bankTransaction("done")]);
    assignTransaction(database, "done", "Wohnen");

    expect(unassignedSpending(database).map((transaction) => transaction.id)).toEqual(["spent"]);
  });

  it("assigns a category or marks a transfer as ignored", () => {
    addTransactions(database, [bankTransaction("a"), bankTransaction("b")]);

    expect(assignTransaction(database, "a", "Freizeit")).toBe(true);
    assignTransaction(database, "b", IGNORED);

    const categories = transactionsInMonth(database, "2026-11").map((transaction) => transaction.category).sort();
    expect(categories).toEqual(["Freizeit", IGNORED]);
  });

  it("reports when the transaction does not exist", () => {
    expect(assignTransaction(database, "missing", "Freizeit")).toBe(false);
  });
});

const INSURANCE: NewBudgetItem = {
  category: "Auto", name: "KFZ-Versicherung", amountCents: 38618, rhythm: "Jahr", validFrom: "2026-01", validUntil: null,
};

describe("budget items", () => {
  it("keeps items in the order they were added", () => {
    addBudgetItem(database, { ...INSURANCE, name: "Erst" });
    addBudgetItem(database, { ...INSURANCE, name: "Dann" });

    expect(budgetItems(database).map((item) => item.name)).toEqual(["Erst", "Dann"]);
  });

  it("stores every field of an item", () => {
    const id = addBudgetItem(database, INSURANCE);

    expect(budgetItems(database)).toEqual([{ id, ...INSURANCE }]);
  });

  it("changes an item", () => {
    const id = addBudgetItem(database, INSURANCE);

    updateBudgetItem(database, { id, ...INSURANCE, amountCents: 97980, validUntil: "2026-12" });

    expect(budgetItems(database)[0]).toMatchObject({ amountCents: 97980, validUntil: "2026-12" });
  });

  it("sends the payments of a removed item back to the monthly spending", () => {
    const id = addBudgetItem(database, INSURANCE);
    addTransactions(database, [bankTransaction("huk")]);
    assignTransaction(database, "huk", "Auto", id);

    deleteBudgetItem(database, id);

    expect(budgetItems(database)).toEqual([]);
    expect(transactionsInMonth(database, "2026-11")[0]).toMatchObject({ category: "Auto", budgetItemId: null });
  });
});

describe("yearly payments", () => {
  it("lists the transactions that pay a yearly item in a year", () => {
    const id = addBudgetItem(database, INSURANCE);
    addTransactions(database, [bankTransaction("huk"), bankTransaction("rewe"), bankTransaction("old", "2025-11-05")]);
    assignTransaction(database, "huk", "Auto", id);
    assignTransaction(database, "old", "Auto", id);
    assignTransaction(database, "rewe", "Täglicher Bedarf");

    expect(yearlyPayments(database, 2026).map((transaction) => transaction.id)).toEqual(["huk"]);
  });
});

describe("migration", () => {
  it("turns the category budgets of version 1 into monthly items", () => {
    const path = `${process.env.TMPDIR ?? "/tmp"}/finanzfuchs-v1-${Date.now()}.db`;
    const old = new DatabaseSync(path);
    old.exec(`
      CREATE TABLE transactions (id TEXT PRIMARY KEY, account TEXT NOT NULL, booking_date TEXT NOT NULL,
        amount_cents INTEGER NOT NULL, counterparty TEXT NOT NULL, purpose TEXT NOT NULL, category TEXT);
      CREATE TABLE budgets (month TEXT NOT NULL, category TEXT NOT NULL, amount_cents INTEGER NOT NULL, PRIMARY KEY (month, category));
      INSERT INTO budgets VALUES ('2026-01', 'Auto', 30000), ('2026-03', 'Auto', 31900), ('2026-03', 'Wohnen', 253100);
      PRAGMA user_version = 1;
    `);
    old.close();

    const migrated = openDatabase(path);

    expect(budgetItems(migrated).map(({ id, ...item }) => item)).toEqual([
      { category: "Auto", name: "Auto", amountCents: 31900, rhythm: "Monat", validFrom: "2026-03", validUntil: null },
      { category: "Wohnen", name: "Wohnen", amountCents: 253100, rhythm: "Monat", validFrom: "2026-03", validUntil: null },
    ]);
  });
});
