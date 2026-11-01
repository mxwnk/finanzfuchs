import { type BudgetItem, yearlyItems } from "./budget-items";
import type { Cents } from "./money";
import type { Month } from "./month";
import type { AssignedTransaction } from "./overview";

const MONTHS_PER_YEAR = 12;

export interface ReserveItem {
  item: BudgetItem;
  paidCents: Cents;
  isPaid: boolean;
}

/** The yearly costs of the chosen month's year: saved up month by month, paid when due. */
export interface Reserve {
  year: number;
  savedCents: Cents;
  paidCents: Cents;
  balanceCents: Cents;
  openCents: Cents;
  yearEndSavedCents: Cents;
  items: ReserveItem[];
}

export function buildReserve(items: BudgetItem[], transactions: AssignedTransaction[], month: Month): Reserve {
  const year = Number(month.slice(0, 4));
  const monthsSoFar = monthsOfYear(year).filter((candidate) => candidate <= month);
  const payments = transactions.filter((transaction) => isPaymentUpTo(transaction, year, month));
  const reserveItems = yearlyItems(items, month).map((item) => toReserveItem(item, payments));
  const savedCents = savedOver(items, monthsSoFar);
  const paidCents = reserveItems.reduce((total, row) => total + row.paidCents, 0);
  return {
    year,
    savedCents,
    paidCents,
    balanceCents: savedCents - paidCents,
    openCents: reserveItems.filter((row) => !row.isPaid).reduce((total, row) => total + row.item.amountCents, 0),
    yearEndSavedCents: savedOver(items, monthsOfYear(year)),
    items: reserveItems,
  };
}

function toReserveItem(item: BudgetItem, payments: AssignedTransaction[]): ReserveItem {
  const paidCents = 0 - payments.filter((p) => p.budgetItemId === item.id).reduce((total, p) => total + p.amountCents, 0);
  return { item, paidCents, isPaid: paidCents > 0 };
}

function savedOver(items: BudgetItem[], months: Month[]): Cents {
  const twelfths = months.flatMap((month) => yearlyItems(items, month).map((item) => item.amountCents / MONTHS_PER_YEAR));
  return Math.round(twelfths.reduce((total, amount) => total + amount, 0));
}

function isPaymentUpTo(transaction: AssignedTransaction, year: number, month: Month): boolean {
  return transaction.budgetItemId !== null && transaction.bookingDate.startsWith(`${year}-`) && transaction.bookingDate.slice(0, 7) <= month;
}

function monthsOfYear(year: number): Month[] {
  return Array.from({ length: MONTHS_PER_YEAR }, (_, index) => `${year}-${String(index + 1).padStart(2, "0")}`);
}
