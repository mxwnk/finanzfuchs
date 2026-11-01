import { useState } from "react";
import { Form, redirect, useNavigation } from "react-router";

import { addBudgetItem, budgetItems, deleteBudgetItem, getDatabase, updateBudgetItem } from "~/.server/database";
import { TrashIcon, UndoIcon } from "~/components/icons";
import { Card } from "~/components/ui";
import { readBudgetForm } from "~/domain/budget-form";
import { type BudgetItem, RHYTHMS, type Rhythm } from "~/domain/budget-items";
import { CATEGORIES, type Category } from "~/domain/categories";
import { formatEuro } from "~/domain/money";
import { monthOf } from "~/domain/month";

import type { Route } from "./+types/budgets";

const MONTHS_PER_YEAR = 12;
const RHYTHM_LABELS: Record<Rhythm, string> = { Monat: "monatlich", Jahr: "jährlich" };
const input = "rounded-lg border border-stone-300 bg-stone-50 px-2.5 py-1.5 focus:border-fox focus:outline-none dark:border-stone-700 dark:bg-stone-800";

export function meta() {
  return [{ title: "Budgets · Finanzfuchs" }];
}

export function loader() {
  const today = monthOf(new Date());
  const items = budgetItems(getDatabase()).filter((item) => item.validUntil === null || item.validUntil >= today);
  return { items };
}

export async function action({ request }: Route.ActionArgs) {
  const form = readBudgetForm(await request.formData(), monthOf(new Date()));
  if (Object.keys(form.errors).length > 0) {
    return { errors: form.errors };
  }
  const database = getDatabase();
  const existing = new Map(budgetItems(database).map((item) => [item.id, item]));
  for (const change of form.changed) {
    const item = existing.get(change.id);
    if (item) updateBudgetItem(database, { ...item, ...change });
  }
  form.added.forEach((item) => addBudgetItem(database, item));
  form.removed.forEach((id) => deleteBudgetItem(database, id));
  return redirect("/");
}

export default function BudgetsPage({ loaderData, actionData }: Route.ComponentProps) {
  const { items } = loaderData;
  const isSaving = useNavigation().state === "submitting";
  const monthlyTotal = sumOf(items, "Monat");
  const yearlyTotal = sumOf(items, "Jahr");
  return (
    <Form method="post" className="space-y-4">
      <Card>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold tracking-wide text-stone-500 uppercase">Monatsbudget</p>
            <p className="num text-2xl font-bold">{formatEuro(monthlyTotal)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs font-semibold tracking-wide text-stone-500 uppercase">Jahresposten</p>
            <p className="num text-2xl font-bold">{formatEuro(yearlyTotal)}</p>
            <p className="text-xs text-stone-500">= {formatEuro(yearlyTotal / MONTHS_PER_YEAR)} im Monat für die Rücklage</p>
          </div>
        </div>
        <p className="mt-3 text-sm text-stone-500">
          Monatliche Posten bilden das Budget eines Monats. Jahresposten werden jeden Monat zu einem Zwölftel angespart und
          aus der Rücklage bezahlt, wenn sie fällig sind.
        </p>
      </Card>

      {CATEGORIES.map((category) => (
        <CategoryItems
          key={category}
          category={category}
          items={items.filter((item) => item.category === category)}
          errors={actionData?.errors ?? {}}
        />
      ))}

      <div className="sticky bottom-[calc(6.25rem+env(safe-area-inset-bottom))] flex justify-end sm:bottom-3">
        <button type="submit" disabled={isSaving} className="rounded-xl bg-fox px-6 py-3 font-semibold text-white shadow-lg hover:brightness-105 disabled:opacity-60">
          {isSaving ? "Speichere …" : "Budgets speichern"}
        </button>
      </div>
    </Form>
  );
}

function CategoryItems({ category, items, errors }: { category: Category; items: BudgetItem[]; errors: Record<string, string> }) {
  const monthly = sumOf(items, "Monat");
  const yearly = sumOf(items, "Jahr");
  return (
    <Card className="!p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h3 className="font-semibold">{category}</h3>
        <p className="num text-sm text-stone-500">
          {formatEuro(monthly)} im Monat{yearly > 0 ? ` · ${formatEuro(yearly)} im Jahr` : ""}
        </p>
      </div>
      <ul className="divide-y divide-stone-200 sm:space-y-2 sm:divide-y-0 dark:divide-stone-800">
        {items.map((item) => (
          <ExistingItem key={item.id} item={item} error={errors[`${item.id}`]} />
        ))}
        <li className="border-t border-dashed border-stone-200 py-3 sm:pt-2 sm:pb-0 dark:border-stone-800">
          <input type="hidden" name="new" value={category} />
          <ItemFields prefix={`new`} category={category} name="" amountCents={null} rhythm="Monat" placeholder="Neuer Posten …" />
          {errors[`new-${category}`] && <p className="text-xs text-red-700">{errors[`new-${category}`]}</p>}
        </li>
      </ul>
    </Card>
  );
}

interface ItemFieldsProps {
  prefix: string;
  category?: Category;
  name: string;
  amountCents: number | null;
  rhythm: Rhythm;
  placeholder?: string;
  /** The button in the last column; new rows leave it empty. */
  action?: React.ReactNode;
}

/**
 * Clicking the bin only marks the item: it is removed when the budgets are saved, so a slip of
 * the finger costs nothing.
 */
function ExistingItem({ item, error }: { item: BudgetItem; error?: string }) {
  const [isMarked, setMarked] = useState(false);
  const removeButton = (
    <button
      type="button"
      onClick={() => setMarked(!isMarked)}
      aria-pressed={isMarked}
      aria-label={isMarked ? `${item.name} behalten` : `${item.name} entfernen`}
      title={isMarked ? "Doch behalten" : "Entfernen"}
      className={`grid size-9 place-items-center rounded-lg border transition ${
        isMarked
          ? "border-stone-300 bg-stone-100 text-stone-700 hover:bg-stone-200 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100 dark:hover:bg-stone-700"
          : "border-transparent text-stone-400 hover:border-red-200 hover:bg-red-50 hover:text-red-600 dark:hover:border-red-900 dark:hover:bg-red-950 dark:hover:text-red-400"
      }`}
    >
      {isMarked ? <UndoIcon /> : <TrashIcon />}
    </button>
  );
  return (
    <li className="py-3 first:pt-0 sm:py-0">
      <input type="hidden" name="item" value={item.id} />
      <input type="hidden" name={`category-${item.id}`} value={item.category} />
      {isMarked && <input type="hidden" name={`remove-${item.id}`} value="on" />}
      <div className={isMarked ? "[&_input]:opacity-50 [&_select]:opacity-50 [&_input:first-child]:line-through" : ""}>
        <ItemFields prefix={`${item.id}`} name={item.name} amountCents={item.amountCents} rhythm={item.rhythm} action={removeButton} />
      </div>
      {isMarked && <p className="mt-1 text-xs text-red-700 dark:text-red-400">Wird beim Speichern entfernt.</p>}
      {error && <p className="text-xs text-red-700">{error}</p>}
    </li>
  );
}

/** Existing items post `name-<id>`, new ones `new-name-<category>`. */
function ItemFields({ prefix, category, name, amountCents, rhythm, placeholder, action }: ItemFieldsProps) {
  const field = (key: string) => (category ? `${prefix}-${key}-${category}` : `${key}-${prefix}`);
  return (
    // Phones: name and bin on top, amount and rhythm below. Wider screens: one row.
    <div className="grid grid-cols-[1fr_1fr_2.25rem] items-center gap-2 sm:grid-cols-[1fr_6.5rem_7.5rem_2.25rem]">
      <input name={field("name")} defaultValue={name} placeholder={placeholder} aria-label="Name" className={`${input} col-span-2 min-w-0 sm:col-span-1`} />
      <input
        name={field("amount")}
        defaultValue={amountCents === null ? "" : String(amountCents / 100).replace(".", ",")}
        inputMode="decimal"
        placeholder="0"
        aria-label="Betrag in Euro"
        className={`${input} num min-w-0 text-right`}
      />
      <select name={field("rhythm")} defaultValue={rhythm} aria-label="Rhythmus" className={`${input} min-w-0`}>
        {RHYTHMS.map((option) => (
          <option key={option} value={option}>
            {RHYTHM_LABELS[option]}
          </option>
        ))}
      </select>
      <div className="col-start-3 row-start-1 sm:col-start-4">{action}</div>
    </div>
  );
}

function sumOf(items: BudgetItem[], rhythm: Rhythm): number {
  return items.filter((item) => item.rhythm === rhythm).reduce((total, item) => total + item.amountCents, 0);
}
