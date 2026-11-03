import { type RouteConfig, index, layout, route } from "@react-router/dev/routes";

export default [
  layout("routes/layout.tsx", [
    index("routes/overview.tsx"),
    route("budgets", "routes/budgets.tsx"),
    route("zuordnen", "routes/assign.tsx"),
    route("import", "routes/import.tsx"),
  ]),
  route("auth/login", "routes/auth.login.ts"),
  route("auth/callback", "routes/auth.callback.tsx"),
  route("auth/logout", "routes/auth.logout.tsx"),
  route("healthz", "routes/healthz.ts"),
] satisfies RouteConfig;
