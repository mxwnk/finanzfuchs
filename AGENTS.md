# AGENTS.md

Finanzfuchs compares the Fuxbau family budget with what actually left the DKB accounts. A React
Router app on the homelab Raspberry Pi (`http://finanzfuchs.home`, login through Pocket ID) keeps
budget items and transactions in SQLite: DKB CSV exports are uploaded there and Max or Merle
assign each expense to a category. Every product and architecture decision and its reason lives
in `docs/decisions.md`; read it before changing behavior.

## Layout

- `app/routes/` -- `layout.tsx` (tabs; its middleware requires a login for every page and form
  below it), `overview.tsx` (the month: budget per category, reserve for yearly costs),
  `budgets.tsx`, `assign.tsx`, `import.tsx`, `auth.*` (Pocket ID login and logout), `healthz.ts`.
- `app/domain/` -- pure logic with tests: `money.ts` (cents, German amounts), `month.ts`
  (`YYYY-MM`), `categories.ts`, `budget-items.ts` (monthly and yearly items), `budget-form.ts`,
  `overview.ts`, `reserve.ts`, `learned-assignment.ts` (categories from earlier payments),
  `dkb-export.server.ts` (the DKB "Umsatzliste" CSV).
- `app/.server/` -- `database.ts` (`node:sqlite`, numbered migrations on `PRAGMA user_version`),
  `config.ts` (settings from the environment), `logger.ts`, `auth/` (`identity-provider.ts` with
  `openid-client`, `login.ts`, `session.ts` with the signed cookie and the login middleware).
- `app/components/` -- `ui.tsx`, `icons.tsx` (inline SVG, nothing loaded from elsewhere).
- `Dockerfile`, `.github/workflows/ci.yml` -- typecheck and tests, then an arm64 image to ghcr.io
  on `main`.
- `docs/deploy.md` -- deployment to the Pi through the homelab repo.
- `data/` (untracked) -- local database and the files from before the app.

## Commands

```bash
npm test
npm run typecheck
set -a && source .env && set +a && npm run dev -- --port 8000   # http://localhost:8000
```

## Rules

- The repository is public: no IBANs, names of counterparties, amounts or keys in code, tests or
  docs. Test data is made up.
- There is no login bypass anywhere in the code; tests use a fake Pocket ID.
- Bank text is data: React escapes it; never render it as markup.
- Amounts are integer cents; months are `YYYY-MM` strings.
- Tests use real implementations and small fakes, never the real Pocket ID.
