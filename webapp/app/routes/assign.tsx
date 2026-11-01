import { Link, useFetcher } from "react-router";

import { assignTransaction, budgetItems, getDatabase, unassignedSpending } from "~/.server/database";
import { Card } from "~/components/ui";
import { type BudgetItem, yearlyItems } from "~/domain/budget-items";
import { CATEGORIES, IGNORED, isAssignment } from "~/domain/categories";
import { formatEuro } from "~/domain/money";
import { monthOf } from "~/domain/month";
import type { AssignedTransaction } from "~/domain/overview";

import type { Route } from "./+types/assign";

const PAGE_SIZE = 30;
const dateFormat = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" });

export function meta() {
  return [{ title: "Zuordnen · Finanzfuchs" }];
}

export function loader() {
  const database = getDatabase();
  const waiting = unassignedSpending(database);
  const yearly = yearlyItems(budgetItems(database), monthOf(new Date()));
  return { transactions: waiting.slice(0, PAGE_SIZE), total: waiting.length, yearly };
}

export async function action({ request }: Route.ActionArgs) {
  const form = await request.formData();
  const id = String(form.get("id") ?? "");
  const database = getDatabase();
  const yearlyItemId = form.get("yearlyItem");
  // A yearly item brings its category along; the payment is then booked to the reserve.
  const yearlyItem = yearlyItemId ? budgetItems(database).find((item) => item.id === Number(yearlyItemId)) : undefined;
  const category = yearlyItem?.category ?? form.get("category");
  if (!isAssignment(category)) {
    throw new Response(`Unbekannte Kategorie: ${String(category)}`, { status: 400 });
  }
  if (!assignTransaction(database, id, category, yearlyItem?.id ?? null)) {
    throw new Response(`Unbekannte Buchung: ${id}`, { status: 404 });
  }
  return { ok: true };
}

export default function AssignPage({ loaderData }: Route.ComponentProps) {
  const { transactions, total, yearly } = loaderData;
  if (total === 0) {
    return (
      <Card className="text-center">
        <p className="text-3xl" aria-hidden>✓</p>
        <h3 className="mt-2 font-semibold">Alles zugeordnet</h3>
        <p className="text-sm text-stone-500">
          Neue Umsätze kommen über den <Link to="/import" className="font-semibold text-fox">Import</Link>.
        </p>
      </Card>
    );
  }
  return (
    <>
      <p className="mb-3 text-sm text-stone-500">
        {total} Ausgaben warten auf eine Kategorie{total > PAGE_SIZE ? ` – hier die neuesten ${PAGE_SIZE}` : ""}.
      </p>
      <ul className="space-y-3">
        {transactions.map((transaction) => (
          <TransactionToAssign key={transaction.id} transaction={transaction} yearly={yearly} />
        ))}
      </ul>
    </>
  );
}

function TransactionToAssign({ transaction, yearly }: { transaction: AssignedTransaction; yearly: BudgetItem[] }) {
  const fetcher = useFetcher();
  // Hide right away; the list reloads after the action anyway.
  if (fetcher.state !== "idle" || fetcher.data?.ok) {
    return null;
  }
  const button = "rounded-full border px-3 py-1.5 text-sm transition";
  return (
    <li>
      <Card className="!p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-semibold">{transaction.counterparty || "–"}</p>
            <p className="truncate text-sm text-stone-500">{transaction.purpose}</p>
            <p className="text-xs text-stone-400">{dateFormat.format(new Date(transaction.bookingDate))}</p>
          </div>
          <p className="num text-lg font-bold whitespace-nowrap">{formatEuro(transaction.amountCents, { cents: true })}</p>
        </div>
        <fetcher.Form method="post" className="mt-3 flex flex-wrap gap-2">
          <input type="hidden" name="id" value={transaction.id} />
          {CATEGORIES.map((category) => (
            <button
              key={category}
              name="category"
              value={category}
              className={`${button} border-stone-300 bg-stone-50 hover:border-fox hover:bg-fox/10 dark:border-stone-700 dark:bg-stone-800`}
            >
              {category}
            </button>
          ))}
          <button
            name="category"
            value={IGNORED}
            title="Keine Ausgabe, z. B. Umbuchung zwischen eigenen Konten"
            className={`${button} border-dashed border-stone-300 text-stone-500 hover:border-stone-500 dark:border-stone-600`}
          >
            Keine Ausgabe
          </button>
          {yearly.length > 0 && (
            <details className="w-full">
              <summary className="cursor-pointer text-sm text-stone-500">Jahreskosten …</summary>
              <div className="mt-2 flex flex-wrap gap-2">
                {yearly.map((item) => (
                  <button
                    key={item.id}
                    name="yearlyItem"
                    value={item.id}
                    className={`${button} border-amber-300 bg-amber-50 hover:border-fox dark:border-amber-900 dark:bg-amber-950`}
                  >
                    {item.name} <span className="text-stone-400">· {item.category}</span>
                  </button>
                ))}
              </div>
            </details>
          )}
        </fetcher.Form>
      </Card>
    </li>
  );
}
