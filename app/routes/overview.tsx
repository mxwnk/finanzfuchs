import { Link } from "react-router";

import { budgetItems, getDatabase, transactionsInMonth, yearlyPayments } from "~/.server/database";
import { requestedMonth } from "~/.server/request";
import { Card, MonthSwitch } from "~/components/ui";
import { monthlyBudgets } from "~/domain/budget-items";
import { formatEuro } from "~/domain/money";
import { monthLabel } from "~/domain/month";
import { buildMonthOverview, type CategoryRow, type MonthOverview } from "~/domain/overview";
import { buildReserve, type Reserve } from "~/domain/reserve";

import type { Route } from "./+types/overview";

export function meta() {
  return [{ title: "Übersicht · Finanzfuchs" }];
}

export function loader({ request }: Route.LoaderArgs) {
  const month = requestedMonth(request);
  const database = getDatabase();
  const items = budgetItems(database);
  const overview = buildMonthOverview(month, monthlyBudgets(items, month), transactionsInMonth(database, month));
  const reserve = buildReserve(items, yearlyPayments(database, Number(month.slice(0, 4))), month);
  return { overview, reserve, hasBudget: items.length > 0 };
}

export default function Overview({ loaderData }: Route.ComponentProps) {
  const { overview, reserve, hasBudget } = loaderData;
  const remaining = overview.totalBudgetCents - overview.totalSpentCents;
  return (
    <>
      <MonthSwitch month={overview.month} path="/" />

      <Card className="mb-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-wide text-stone-500 uppercase">Ausgegeben</p>
            <p className="num text-4xl font-bold tracking-tight">{formatEuro(overview.totalSpentCents)}</p>
            <p className="text-sm text-stone-500">von {formatEuro(overview.totalBudgetCents)} Budget</p>
          </div>
          <div className="text-right">
            <p className="text-xs font-semibold tracking-wide text-stone-500 uppercase">{remaining >= 0 ? "Noch übrig" : "Über Budget"}</p>
            <p className={`num text-2xl font-bold ${remaining >= 0 ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"}`}>
              {formatEuro(Math.abs(remaining))}
            </p>
          </div>
        </div>
        <Bar spentCents={overview.totalSpentCents} budgetCents={overview.totalBudgetCents} large />
        <Hints overview={overview} hasBudget={hasBudget} />
      </Card>

      <Card className="mb-4">
        <h3 className="mb-3 font-semibold">Kategorien</h3>
        <ul className="space-y-4">
          {overview.categories.map((row) => (
            <CategoryLine key={row.category} row={row} />
          ))}
        </ul>
      </Card>

      {reserve.items.length > 0 && <ReserveCard reserve={reserve} />}
    </>
  );
}

function ReserveCard({ reserve }: { reserve: Reserve }) {
  const isShort = reserve.balanceCents < 0;
  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold">Rücklage für Jahreskosten {reserve.year}</h3>
        <p className={`num text-lg font-bold ${isShort ? "text-red-700 dark:text-red-400" : "text-green-700 dark:text-green-400"}`}>
          {formatEuro(reserve.balanceCents)}
        </p>
      </div>
      <p className="mb-3 text-sm text-stone-500">
        Angespart {formatEuro(reserve.savedCents)} · bezahlt {formatEuro(reserve.paidCents)} · noch fällig {formatEuro(reserve.openCents)}
        {isShort ? " – mehr bezahlt als bisher angespart" : ""}
      </p>
      <ul className="divide-y divide-stone-200 dark:divide-stone-800">
        {reserve.items.map(({ item, paidCents, isPaid }) => (
          <li key={item.id} className="flex items-center justify-between gap-3 py-2 text-sm">
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className={`grid size-6 place-items-center rounded-full text-xs font-bold ${
                  isPaid ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" : "bg-stone-200 text-stone-500 dark:bg-stone-800"
                }`}
              >
                {isPaid ? "✓" : "…"}
              </span>
              <span>
                {item.name} <span className="text-stone-400">· {item.category}</span>
                <span className="sr-only">{isPaid ? " – bezahlt" : " – offen"}</span>
              </span>
            </span>
            <span className="num whitespace-nowrap">
              {isPaid ? (
                <span className={paidCents > item.amountCents ? "font-semibold text-red-700 dark:text-red-400" : ""}>{formatEuro(paidCents)}</span>
              ) : (
                <span className="text-stone-400">{formatEuro(item.amountCents)}</span>
              )}
              {isPaid && paidCents !== item.amountCents && <span className="text-stone-400"> von {formatEuro(item.amountCents)}</span>}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function CategoryLine({ row }: { row: CategoryRow }) {
  const isOver = row.remainingCents < 0;
  return (
    <li>
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-medium">{row.category}</span>
        <span className="num text-sm font-semibold whitespace-nowrap">
          {formatEuro(row.spentCents)} <span className="font-normal text-stone-500">von {formatEuro(row.budgetCents)}</span>
        </span>
      </div>
      <Bar spentCents={row.spentCents} budgetCents={row.budgetCents} />
      <p className={`mt-1 text-right text-xs ${isOver ? "font-semibold text-red-700 dark:text-red-400" : "text-stone-500"}`}>
        {row.budgetCents === 0 && row.spentCents === 0
          ? "kein Budget"
          : isOver
            ? `${formatEuro(-row.remainingCents)} drüber`
            : `noch ${formatEuro(row.remainingCents)}`}
      </p>
    </li>
  );
}

function Bar({ spentCents, budgetCents, large = false }: { spentCents: number; budgetCents: number; large?: boolean }) {
  const share = budgetCents > 0 ? Math.min(spentCents / budgetCents, 1) : spentCents > 0 ? 1 : 0;
  const isOver = spentCents > budgetCents;
  return (
    <div className={`mt-2 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800 ${large ? "h-3" : "h-2"}`}>
      <div
        className={`h-full rounded-full transition-all ${isOver ? "bg-red-600" : "bg-green-600"}`}
        style={{ width: `${Math.max(share * 100, 0)}%` }}
      />
    </div>
  );
}

function Hints({ overview, hasBudget }: { overview: MonthOverview; hasBudget: boolean }) {
  return (
    <div className="mt-3 space-y-1 text-sm text-stone-500">
      {overview.transactionCount === 0 && (
        <p>
          Für {monthLabel(overview.month)} gibt es noch keine Buchungen. <Link to="/import" className="font-semibold text-fox">Umsätze importieren →</Link>
        </p>
      )}
      {overview.unassignedCount > 0 && (
        <p>
          {overview.unassignedCount} Ausgaben über {formatEuro(overview.unassignedCents)} sind noch keiner Kategorie zugeordnet.{" "}
          <Link to="/zuordnen" className="font-semibold text-fox">Zuordnen →</Link>
        </p>
      )}
      {!hasBudget && (
        <p>
          Noch keine Budgets. <Link to="/budgets" className="font-semibold text-fox">Budgets einstellen →</Link>
        </p>
      )}
    </div>
  );
}
