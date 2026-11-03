import { useState } from "react";
import { Form, redirect, useNavigation } from "react-router";

import { addBudgetItem, budgetItems, deleteBudgetItem, getDatabase, updateBudgetItem } from "~/.server/database";
import { TrashIcon, UndoIcon } from "~/components/icons";
import { Card } from "~/components/ui";
import { readBudgetForm } from "~/domain/budget-form";
import type { BudgetItem, Rhythm } from "~/domain/budget-items";
import { CATEGORIES, type Category } from "~/domain/categories";
import { formatEuro } from "~/domain/money";
import { monthOf } from "~/domain/month";

import type { Route } from "./+types/budgets";

const MONTHS_PER_YEAR = 12;
const input = "min-w-0 rounded-lg border border-stone-300 bg-stone-50 px-2 py-1.5 focus:border-fox focus:outline-none sm:px-2.5 dark:border-stone-700 dark:bg-stone-800";

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
    <Card className="!p-3 sm:!p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h3 className="font-semibold">{category}</h3>
        <p className="num text-sm text-stone-500">
          {formatEuro(monthly)} im Monat{yearly > 0 ? ` · ${formatEuro(yearly)} im Jahr` : ""}
        </p>
      </div>
      <ul className="space-y-2">
        {items.map((item) => (
          <ExistingItem key={item.id} item={item} error={errors[`${item.id}`]} />
        ))}
        <li className="border-t border-dashed border-stone-200 pt-2 dark:border-stone-800">
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
      className={`grid size-8 place-items-center rounded-lg border transition sm:size-9 ${
        isMarked
          ? "border-stone-300 bg-stone-100 text-stone-700 hover:bg-stone-200 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100 dark:hover:bg-stone-700"
          : "border-transparent text-stone-400 hover:border-red-200 hover:bg-red-50 hover:text-red-600 dark:hover:border-red-900 dark:hover:bg-red-950 dark:hover:text-red-400"
      }`}
    >
      {isMarked ? <UndoIcon /> : <TrashIcon />}
    </button>
  );
  return (
    <li>
      <input type="hidden" name="item" value={item.id} />
      <input type="hidden" name={`category-${item.id}`} value={item.category} />
      {isMarked && <input type="hidden" name={`remove-${item.id}`} value="on" />}
      <div className={isMarked ? "[&_[data-rhythm]]:opacity-50 [&_input]:opacity-50 [&_input:first-child]:line-through" : ""}>
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
    // One row everywhere; on phones amount and rhythm get just the room their content needs.
    <div className="grid grid-cols-[minmax(0,1fr)_5.25rem_3.25rem_2rem] items-center gap-1.5 sm:grid-cols-[1fr_6.5rem_5rem_2.25rem] sm:gap-2">
      <input name={field("name")} defaultValue={name} placeholder={placeholder} aria-label="Name" className={input} />
      <input
        name={field("amount")}
        defaultValue={amountCents === null ? "" : String(amountCents / 100).replace(".", ",")}
        inputMode="decimal"
        placeholder="0"
        aria-label="Betrag in Euro"
        className={`${input} num px-1.5 text-right sm:px-2.5`}
      />
      <RhythmToggle name={field("rhythm")} initial={rhythm} />
      <div>{action}</div>
    </div>
  );
}

/**
 * Monthly or yearly as one tap instead of a select: no dropdown arrow, so it fits a phone row.
 * A hidden input carries the value into the form.
 */
function RhythmToggle({ name, initial }: { name: string; initial: Rhythm }) {
  const [rhythm, setRhythm] = useState<Rhythm>(initial);
  const isYearly = rhythm === "Jahr";
  return (
    <>
      <input type="hidden" name={name} value={rhythm} />
      <button
        type="button"
        data-rhythm
        onClick={() => setRhythm(isYearly ? "Monat" : "Jahr")}
        aria-label={`Rhythmus: ${isYearly ? "jährlich" : "monatlich"} – antippen zum Wechseln`}
        className={`h-full rounded-lg border px-1 text-[13px] font-semibold transition active:scale-95 sm:text-sm ${
          isYearly
            ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
            : "border-stone-300 bg-stone-50 text-stone-700 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200"
        }`}
      >
        {rhythm}
      </button>
    </>
  );
}

function sumOf(items: BudgetItem[], rhythm: Rhythm): number {
  return items.filter((item) => item.rhythm === rhythm).reduce((total, item) => total + item.amountCents, 0);
}
