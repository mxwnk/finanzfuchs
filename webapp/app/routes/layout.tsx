import { NavLink, Outlet } from "react-router";

const TABS = [
  { to: "/", label: "Übersicht", end: true },
  { to: "/budgets", label: "Budgets", end: false },
  { to: "/zuordnen", label: "Zuordnen", end: false },
  { to: "/import", label: "Import", end: false },
];

export default function Layout() {
  return (
    <div className="mx-auto min-h-screen max-w-3xl px-4 pb-12">
      <header className="flex items-center gap-3 pt-5 pb-4">
        <div className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-fox to-fox-dark text-lg shadow-md shadow-fox/30" aria-hidden>
          🦊
        </div>
        <h1 className="text-lg font-bold tracking-tight">Finanzfuchs</h1>
      </header>
      <nav aria-label="Bereiche" className="sticky top-0 z-10 -mx-4 mb-5 bg-stone-100/90 px-4 py-2 backdrop-blur dark:bg-stone-950/90">
        <div className="grid grid-cols-4 gap-1 rounded-xl bg-stone-200 p-1 dark:bg-stone-800">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                `rounded-lg px-2 py-2 text-center text-sm font-medium transition ${
                  isActive
                    ? "bg-white font-semibold text-stone-900 shadow-sm dark:bg-stone-700 dark:text-white"
                    : "text-stone-600 hover:text-stone-900 dark:text-stone-300 dark:hover:text-white"
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <Outlet />
    </div>
  );
}
