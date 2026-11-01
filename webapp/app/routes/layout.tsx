import { NavLink, Outlet } from "react-router";

import { countUnassignedSpending, getDatabase } from "~/.server/database";
import { AssignIcon, BudgetIcon, ImportIcon, OverviewIcon } from "~/components/icons";

import type { Route } from "./+types/layout";

const TABS = [
  { to: "/", label: "Übersicht", Icon: OverviewIcon, end: true, showsOpenCount: false },
  { to: "/budgets", label: "Budgets", Icon: BudgetIcon, end: false, showsOpenCount: false },
  { to: "/zuordnen", label: "Zuordnen", Icon: AssignIcon, end: false, showsOpenCount: true },
  { to: "/import", label: "Import", Icon: ImportIcon, end: false, showsOpenCount: false },
];
const BADGE_LIMIT = 99;

export function loader() {
  return { openCount: countUnassignedSpending(getDatabase()) };
}

export default function Layout({ loaderData }: Route.ComponentProps) {
  const { openCount } = loaderData;
  return (
    // On phones the page leaves room for the floating tab bar and the home indicator.
    <div className="mx-auto min-h-screen max-w-3xl px-4 pb-[calc(6.5rem+env(safe-area-inset-bottom))] sm:pb-12">
      <header className="flex items-center gap-3 pt-5 pb-4">
        <div className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-fox to-fox-dark text-lg shadow-md shadow-fox/30" aria-hidden>
          🦊
        </div>
        <h1 className="text-lg font-bold tracking-tight">Finanzfuchs</h1>
      </header>
      <TopTabs openCount={openCount} />
      <Outlet />
      <BottomTabs openCount={openCount} />
    </div>
  );
}

/** Wide screens: a segmented control above the content. */
function TopTabs({ openCount }: { openCount: number }) {
  return (
    <nav aria-label="Bereiche" className="sticky top-0 z-10 -mx-4 mb-5 hidden bg-stone-100/90 px-4 py-2 backdrop-blur sm:block dark:bg-stone-950/90">
      <div className="grid grid-cols-4 gap-1 rounded-xl bg-stone-200 p-1 dark:bg-stone-800">
        {TABS.map(({ to, label, Icon, end, showsOpenCount }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center justify-center gap-2 rounded-lg px-2 py-2 text-sm font-medium transition ${
                isActive
                  ? "bg-white font-semibold text-stone-900 shadow-sm dark:bg-stone-700 dark:text-white"
                  : "text-stone-600 hover:text-stone-900 dark:text-stone-300 dark:hover:text-white"
              }`
            }
          >
            <Icon className="size-4" />
            {label}
            {showsOpenCount && openCount > 0 && <Badge count={openCount} />}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

/** Phones: a floating bar at the thumb, above the home indicator. */
function BottomTabs({ openCount }: { openCount: number }) {
  return (
    <nav
      aria-label="Bereiche"
      className="fixed inset-x-3 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] z-20 grid grid-cols-4 rounded-3xl border border-white/60 bg-white/75 p-1.5 shadow-xl shadow-stone-900/10 backdrop-blur-xl sm:hidden dark:border-white/10 dark:bg-stone-900/75 dark:shadow-black/40"
    >
      {TABS.map(({ to, label, Icon, end, showsOpenCount }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `group relative flex flex-col items-center gap-0.5 rounded-2xl py-2 text-[11px] font-semibold transition active:scale-95 ${
              isActive ? "bg-fox/12 text-fox" : "text-stone-500 dark:text-stone-400"
            }`
          }
        >
          <span className="relative">
            <Icon className="size-6 transition group-aria-[current=page]:scale-110" />
            {showsOpenCount && openCount > 0 && (
              <span className="absolute -top-1.5 -right-3">
                <Badge count={openCount} />
              </span>
            )}
          </span>
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function Badge({ count }: { count: number }) {
  return (
    <span
      className="num min-w-5 rounded-full bg-red-600 px-1.5 text-center text-[10.5px] leading-5 font-bold text-white shadow-sm"
      aria-label={`${count} offen`}
    >
      {count > BADGE_LIMIT ? `${BADGE_LIMIT}+` : count}
    </span>
  );
}
