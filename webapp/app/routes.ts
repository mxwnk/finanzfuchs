import { type RouteConfig, index, layout, route } from "@react-router/dev/routes";

export default [
  layout("routes/layout.tsx", [
    index("routes/overview.tsx"),
    route("budgets", "routes/budgets.tsx"),
    route("zuordnen", "routes/assign.tsx"),
    route("import", "routes/import.tsx"),
  ]),
] satisfies RouteConfig;
