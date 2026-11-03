import { isRouteErrorResponse, Links, Meta, Outlet, Scripts, ScrollRestoration } from "react-router";

import type { Route } from "./+types/root";
import "./app.css";

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <meta name="theme-color" content="#eb6834" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const isNotFound = isRouteErrorResponse(error) && error.status === 404;
  const details = import.meta.env.DEV && error instanceof Error ? error.message : undefined;
  return (
    <main className="mx-auto max-w-xl p-6">
      <h1 className="text-xl font-bold">{isNotFound ? "Seite nicht gefunden" : "Da ist etwas schiefgegangen"}</h1>
      {details && <pre className="mt-4 overflow-x-auto rounded-lg bg-stone-100 p-4 text-sm">{details}</pre>}
    </main>
  );
}
