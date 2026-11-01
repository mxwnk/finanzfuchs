import { Link } from "react-router";

import { type Month, monthLabel, shiftMonth } from "~/domain/month";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900 ${className}`}>
      {children}
    </section>
  );
}

/** Previous and next month as links; `path` is the page they stay on. */
export function MonthSwitch({ month, path }: { month: Month; path: string }) {
  const arrow = "grid size-10 place-items-center rounded-xl border border-stone-200 bg-white text-xl hover:border-stone-400 dark:border-stone-700 dark:bg-stone-900";
  return (
    <div className="mb-4 flex items-center justify-between">
      <Link to={`${path}?monat=${shiftMonth(month, -1)}`} className={arrow} aria-label="Vormonat">‹</Link>
      <h2 className="text-xl font-bold tracking-tight">{monthLabel(month)}</h2>
      <Link to={`${path}?monat=${shiftMonth(month, 1)}`} className={arrow} aria-label="Folgemonat">›</Link>
    </div>
  );
}
