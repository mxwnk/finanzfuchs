import { type BudgetItem, isRhythm, type Rhythm } from "./budget-items";
import { CATEGORIES, type Category } from "./categories";
import { AmountError, parseGermanAmount } from "./money";
import type { Month } from "./month";

/** What the user may change on an existing item; validity stays as it was. */
export type ItemChange = Pick<BudgetItem, "id" | "category" | "name" | "amountCents" | "rhythm">;
export type NewItem = Omit<BudgetItem, "id">;

export interface BudgetForm {
  changed: ItemChange[];
  added: NewItem[];
  removed: number[];
  /** Keyed by item id, or by `new-<category>` for a new item. */
  errors: Record<string, string>;
}

/**
 * The budgets page posts every item as `<field>-<id>` plus one empty row per category as
 * `new-<field>-<category>`; an empty new row means nothing is added.
 */
export function readBudgetForm(form: FormData, month: Month): BudgetForm {
  const result: BudgetForm = { changed: [], added: [], removed: [], errors: {} };
  for (const idText of form.getAll("item").map(String)) {
    const id = Number(idText);
    if (form.get(`remove-${id}`)) {
      result.removed.push(id);
      continue;
    }
    readFields(form, `${id}`, (fields) => result.changed.push({ id, ...fields }), result.errors);
  }
  for (const category of form.getAll("new").map(String)) {
    if (!String(form.get(`new-name-${category}`) ?? "").trim()) continue;
    readFields(form, `new-${category}`, (fields) => result.added.push({ ...fields, validFrom: month, validUntil: null }), result.errors, category);
  }
  return result;
}

type Fields = { category: Category; name: string; amountCents: number; rhythm: Rhythm };

function readFields(form: FormData, key: string, accept: (fields: Fields) => void, errors: Record<string, string>, newCategory?: string): void {
  const field = (name: string) => String(form.get(newCategory ? `new-${name}-${newCategory}` : `${name}-${key}`) ?? "").trim();
  const category = newCategory ?? field("category");
  const name = field("name");
  const rhythm = field("rhythm");
  if (!CATEGORIES.includes(category as Category) || !isRhythm(rhythm)) {
    errors[key] = "Kategorie oder Rhythmus fehlt";
    return;
  }
  if (!name) {
    errors[key] = "Name fehlt";
    return;
  }
  try {
    accept({ category: category as Category, name, amountCents: parseGermanAmount(field("amount") || "0"), rhythm });
  } catch (error) {
    if (!(error instanceof AmountError)) throw error;
    errors[key] = error.message;
  }
}
