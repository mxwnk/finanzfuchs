import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

import type { BudgetItem } from "~/domain/budget-items";
import type { Assignment } from "~/domain/categories";
import type { BankTransaction } from "~/domain/dkb-export.server";
import type { Month } from "~/domain/month";
import type { AssignedTransaction } from "~/domain/overview";

export type Database = DatabaseSync;

const DEFAULT_PATH = "data/finanzfuchs.db";

const INITIAL_SCHEMA = `
  CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    booking_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    counterparty TEXT NOT NULL,
    purpose TEXT NOT NULL,
    category TEXT
  );
  CREATE INDEX transactions_by_date ON transactions (booking_date);
  CREATE TABLE budgets (
    month TEXT NOT NULL,
    category TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    PRIMARY KEY (month, category)
  );
`;

export function openDatabase(path: string): Database {
  if (path !== ":memory:") {
    mkdirSync(dirname(path), { recursive: true });
  }
  const database = new DatabaseSync(path);
  migrate(database);
  return database;
}

let shared: Database | undefined;

/** The app's database; `FINANZFUCHS_DATABASE` overrides the path. */
export function getDatabase(): Database {
  shared ??= openDatabase(process.env.FINANZFUCHS_DATABASE ?? DEFAULT_PATH);
  return shared;
}

/** Returns how many of the given transactions were new. */
export function addTransactions(database: Database, transactions: BankTransaction[]): number {
  const insert = database.prepare(
    `INSERT OR IGNORE INTO transactions (id, account, booking_date, amount_cents, counterparty, purpose)
     VALUES (?, ?, ?, ?, ?, ?)`,
  );
  let added = 0;
  inTransaction(database, () => {
    for (const transaction of transactions) {
      const result = insert.run(transaction.id, transaction.account, transaction.bookingDate,
        transaction.amountCents, transaction.counterparty, transaction.purpose);
      added += Number(result.changes);
    }
  });
  return added;
}

export function transactionsInMonth(database: Database, month: Month): AssignedTransaction[] {
  const rows = database
    .prepare(`SELECT * FROM transactions WHERE booking_date LIKE ? ORDER BY booking_date DESC, rowid DESC`)
    .all(`${month}-%`);
  return rows.map(toAssignedTransaction);
}

/** How many outgoing transactions still wait for a category; cheap enough for every page. */
export function countUnassignedSpending(database: Database): number {
  const row = database.prepare(`SELECT COUNT(*) AS open FROM transactions WHERE category IS NULL AND amount_cents < 0`).get() as { open: number };
  return row.open;
}

/** Money that left the account and still waits for a category, newest first. */
export function unassignedSpending(database: Database): AssignedTransaction[] {
  const rows = database
    .prepare(`SELECT * FROM transactions WHERE category IS NULL AND amount_cents < 0 ORDER BY booking_date DESC, rowid DESC`)
    .all();
  return rows.map(toAssignedTransaction);
}

/**
 * Returns false when there is no such transaction. `budgetItemId` marks a payment of a yearly
 * item, which is paid from the reserve instead of the month's budget.
 */
export function assignTransaction(database: Database, id: string, assignment: Assignment, budgetItemId: number | null = null): boolean {
  const result = database
    .prepare(`UPDATE transactions SET category = ?, budget_item_id = ? WHERE id = ?`)
    .run(assignment, budgetItemId, id);
  return Number(result.changes) > 0;
}

/** All payments of yearly items in a year, for the reserve. */
export function yearlyPayments(database: Database, year: number): AssignedTransaction[] {
  const rows = database
    .prepare(`SELECT * FROM transactions WHERE budget_item_id IS NOT NULL AND booking_date LIKE ?`)
    .all(`${year}-%`);
  return rows.map(toAssignedTransaction);
}

export function budgetItems(database: Database): BudgetItem[] {
  const rows = database.prepare(`SELECT * FROM budget_items ORDER BY position, id`).all();
  return rows.map(toBudgetItem);
}

export type NewBudgetItem = Omit<BudgetItem, "id">;

export function addBudgetItem(database: Database, item: NewBudgetItem): number {
  const { next } = database.prepare(`SELECT COALESCE(MAX(position), 0) + 1 AS next FROM budget_items`).get() as { next: number };
  const result = database
    .prepare(`INSERT INTO budget_items (category, name, amount_cents, rhythm, valid_from, valid_until, position) VALUES (?, ?, ?, ?, ?, ?, ?)`)
    .run(item.category, item.name, item.amountCents, item.rhythm, item.validFrom, item.validUntil, next);
  return Number(result.lastInsertRowid);
}

export function updateBudgetItem(database: Database, item: BudgetItem): void {
  database
    .prepare(`UPDATE budget_items SET category = ?, name = ?, amount_cents = ?, rhythm = ?, valid_from = ?, valid_until = ? WHERE id = ?`)
    .run(item.category, item.name, item.amountCents, item.rhythm, item.validFrom, item.validUntil, item.id);
}

/** Payments of a removed yearly item go back to their category's monthly spending. */
export function deleteBudgetItem(database: Database, id: number): void {
  inTransaction(database, () => {
    database.prepare(`UPDATE transactions SET budget_item_id = NULL WHERE budget_item_id = ?`).run(id);
    database.prepare(`DELETE FROM budget_items WHERE id = ?`).run(id);
  });
}

/** Version 2: budgets become items with a rhythm, like the rows of the old Excel. */
const BUDGET_ITEMS = `
  CREATE TABLE budget_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    rhythm TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    position INTEGER NOT NULL
  );
  ALTER TABLE transactions ADD COLUMN budget_item_id INTEGER REFERENCES budget_items (id);
  INSERT INTO budget_items (category, name, amount_cents, rhythm, valid_from, position)
    SELECT category, category, amount_cents, 'Monat', month, ROW_NUMBER() OVER (ORDER BY category)
    FROM budgets WHERE month = (SELECT MAX(month) FROM budgets);
  DROP TABLE budgets;
`;

const MIGRATIONS = [INITIAL_SCHEMA, BUDGET_ITEMS];

/** Runs every schema step the database lacks; `user_version` counts the steps done. */
function migrate(database: Database): void {
  const { user_version: version } = database.prepare("PRAGMA user_version").get() as { user_version: number };
  MIGRATIONS.slice(version).forEach((step, index) => {
    inTransaction(database, () => {
      database.exec(step);
      database.exec(`PRAGMA user_version = ${version + index + 1}`);
    });
  });
}

function inTransaction(database: Database, work: () => void): void {
  database.exec("BEGIN");
  try {
    work();
    database.exec("COMMIT");
  } catch (error) {
    database.exec("ROLLBACK");
    throw error;
  }
}

function toAssignedTransaction(row: Record<string, unknown>): AssignedTransaction {
  return {
    id: String(row.id),
    bookingDate: String(row.booking_date),
    amountCents: Number(row.amount_cents),
    counterparty: String(row.counterparty),
    purpose: String(row.purpose),
    category: (row.category as Assignment | null) ?? null,
    budgetItemId: row.budget_item_id === null || row.budget_item_id === undefined ? null : Number(row.budget_item_id),
  };
}

function toBudgetItem(row: Record<string, unknown>): BudgetItem {
  return {
    id: Number(row.id),
    category: row.category as BudgetItem["category"],
    name: String(row.name),
    amountCents: Number(row.amount_cents),
    rhythm: row.rhythm as BudgetItem["rhythm"],
    validFrom: String(row.valid_from),
    validUntil: row.valid_until === null ? null : String(row.valid_until),
  };
}
