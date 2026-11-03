import type { Category } from "./categories";
import type { Cents } from "./money";
import type { Month } from "./month";

export const RHYTHMS = ["Monat", "Jahr"] as const;
export type Rhythm = (typeof RHYTHMS)[number];

/**
 * One line of the budget, like a row of the old Excel: what is planned for what, and how often.
 * Monthly items make up the month's budget; yearly items are saved up in the reserve.
 */
export interface BudgetItem {
  id: number;
  category: Category;
  name: string;
  amountCents: Cents;
  rhythm: Rhythm;
  validFrom: Month;
  validUntil: Month | null;
}

export type Budgets = Partial<Record<Category, Cents>>;

export function isRhythm(value: unknown): value is Rhythm {
  return RHYTHMS.includes(value as Rhythm);
}

export function validItems(items: BudgetItem[], month: Month): BudgetItem[] {
  return items.filter((item) => item.validFrom <= month && (item.validUntil === null || item.validUntil >= month));
}

export function monthlyBudgets(items: BudgetItem[], month: Month): Budgets {
  const budgets: Budgets = {};
  for (const item of validItems(items, month)) {
    if (item.rhythm === "Monat") {
      budgets[item.category] = (budgets[item.category] ?? 0) + item.amountCents;
    }
  }
  return budgets;
}

export function yearlyItems(items: BudgetItem[], month: Month): BudgetItem[] {
  return validItems(items, month).filter((item) => item.rhythm === "Jahr");
}
