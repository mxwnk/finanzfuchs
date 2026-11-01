# AGENTS.md

Finanzfuchs compares the Fuxbau family budget plan with what actually happened on the DKB
accounts. A web app on the homelab Raspberry Pi (`http://finanzfuchs.home`, login through Pocket
ID) holds plan, rules and transactions in SQLite: DKB CSV exports are uploaded there, rules
assign them, and Max or Merle assign the rest by hand. Every product and architecture decision
and its reason lives in `docs/decisions.md`; read it before changing behavior.

## Layout

- `finanzfuchs/web/` -- FastAPI app: `app.py` (wiring), `context.py` (shared state, login
  checks as `PageUser`/`ApiUser`/`Context`), `auth.py` + `oidc.py` (Pocket ID login, taken from
  the Fuxbau app), `login_routes.py`, `page_routes.py` (year view, import, plan, Excel),
  `api_routes.py` (assigning), `month_routes.py` (start page), `plan_form.py`, `formatting.py`
  (German numbers for templates), `templates/`, `static/` (`app.css`, `nav.css` shared with the
  year dashboard, `assign.js`, `month.js`, manifest and icons).
- `finanzfuchs/storage/` -- SQLite: `database.py` (schema, numbered migrations on
  `PRAGMA user_version`, one connection per unit of work), `plan_store.py`, `rule_store.py`,
  `transaction_store.py`, `session_store.py`, `money.py` (amounts as cents).
- `finanzfuchs/month_view.py` -- how a month is going (budgets with pace, fixed items, pot,
  unplanned); pure, rendered by `web/month_routes.py` and `templates/month.html`.
- `finanzfuchs/importing.py` -- DKB export into the database, then rules.
- `finanzfuchs/assignment/` -- `rules.py` (first match wins; pure), `service.py` (assign by rule,
  by hand, remember as rule, confirm a doubt).
- `finanzfuchs/ledger.py` -- `LedgerEntry`: a transaction with plan line, source and note.
- `finanzfuchs/imports/dkb_csv.py` -- the DKB CSV export ("Umsatzliste") to `BankTransaction`.
- `finanzfuchs/dashboard/` -- the year view (`/jahr`): `dataset.py`, `render.py`, `template.html`
  (charts, filters and aggregation in the page), `vendor/echarts.min.js` (ECharts 5.5.1,
  Apache-2.0, from the npm package after checking its registry integrity).
- `finanzfuchs/export.py` -- the Excel export.
- `finanzfuchs/seeding.py` -- one-time takeover of `plan.csv`, `rules.csv` and DKB exports.
- `finanzfuchs/banking/`, `archive.py`, `sync.py` -- Enable Banking (prepared, not used yet).
- `finanzfuchs/config.py` -- settings from the environment; `.env.example` lists them.
- `finanzfuchs/cli.py` -- `import`, `seed`, `serve`, `connect`, `accounts`, `fetch`.
- `Dockerfile`, `.github/workflows/ci.yml` -- tests, then an arm64 image to ghcr.io on `main`.
- `docs/deploy.md` -- deployment to the Pi through the homelab repo.
- `data/` (untracked) -- local database, DKB exports and the files from before the app.

## Commands

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run finanzfuchs seed data          # once, into data/finanzfuchs.sqlite3
set -a && source .env && set +a && uv run finanzfuchs serve
```

## Rules

- The repository is public: no IBANs, names of counterparties, amounts or keys in code, tests or
  docs. Test data is made up.
- There is no login bypass anywhere in the code; tests use a fake Pocket ID.
- Bank text is data: it is escaped in templates and never trusted as markup.
- Rules never change an assignment made by hand (`AssignmentSource.MANUAL`).
- Raw bank responses are archived before anything parses them, and never overwritten.
- Tests use fakes (`httpx.MockTransport`, small fake classes), never the real bank or Pocket ID.
