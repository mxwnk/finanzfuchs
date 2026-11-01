import type { Budgets } from "./budget-items";
import { type Assignment, CATEGORIES, type Category } from "./categories";
import type { Cents } from "./money";
import { type Month, monthOf } from "./month";

export interface AssignedTransaction {
  id: string;
  bookingDate: string;
  amountCents: Cents;
  counterparty: string;
  purpose: string;
  category: Assignment | null;
  /** Set when the transaction pays a yearly budget item; it is then paid from the reserve. */
  budgetItemId: number | null;
}

export interface CategoryRow {
  category: Category;
  budgetCents: Cents;
  spentCents: Cents;
  remainingCents: Cents;
}

export interface MonthOverview {
  month: Month;
  categories: CategoryRow[];
  totalBudgetCents: Cents;
  totalSpentCents: Cents;
  unassignedCount: number;
  unassignedCents: Cents;
  transactionCount: number;
}

/**
 * Spending is money that left the account; a refund on the same category reduces it. Payments of
 * yearly items stay out: they come from the reserve, not from the month's budget.
 */
export function buildMonthOverview(month: Month, budgets: Budgets, transactions: AssignedTransaction[]): MonthOverview {
  const inMonth = transactions.filter((transaction) => monthOf(transaction.bookingDate) === month);
  const monthlySpending = inMonth.filter((transaction) => transaction.budgetItemId === null);
  const categories = CATEGORIES.map((category) => categoryRow(category, budgets, monthlySpending));
  const unassigned = inMonth.filter(isUnassignedSpending);
  const unassignedCents = sumSpent(unassigned);
  return {
    month,
    categories,
    totalBudgetCents: sum(categories.map((row) => row.budgetCents)),
    totalSpentCents: sum(categories.map((row) => row.spentCents)) + unassignedCents,
    unassignedCount: unassigned.length,
    unassignedCents,
    transactionCount: inMonth.length,
  };
}

export function isUnassignedSpending(transaction: AssignedTransaction): boolean {
  return transaction.category === null && transaction.amountCents < 0;
}

function categoryRow(category: Category, budgets: Budgets, inMonth: AssignedTransaction[]): CategoryRow {
  const budgetCents = budgets[category] ?? 0;
  const spentCents = sumSpent(inMonth.filter((transaction) => transaction.category === category));
  return { category, budgetCents, spentCents, remainingCents: budgetCents - spentCents };
}

function sumSpent(transactions: AssignedTransaction[]): Cents {
  // Subtracting from 0 avoids -0 for an empty list.
  return 0 - sum(transactions.map((transaction) => transaction.amountCents));
}

function sum(values: Cents[]): Cents {
  return values.reduce((total, value) => total + value, 0);
}

