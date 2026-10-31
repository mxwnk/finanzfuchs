# AGENTS.md

Bauplan compares the Fuxbau family budget plan with what actually happened on the DKB accounts.
A service on the homelab NUC fetches transactions through Enable Banking; a Google Sheet is the
frontend. Every product and architecture decision and its reason lives in `docs/decisions.md`;
read it before changing behavior. `Fuxbau Finanzen.xlsx` is the old plan, kept as an archive.

## Layout

- `bauplan/banking/` -- Enable Banking: `authorization.py` (JWT, consent length, reading the
  redirect; pure), `client.py` (HTTP), `transactions.py` (raw transaction to `BankTransaction`).
- `bauplan/imports/dkb_csv.py` -- the DKB CSV export ("Umsatzliste") to `BankTransaction`.
- `bauplan/ledger.py` -- the local journal `data/transactions.csv`; skips known and pending rows.
- `bauplan/assignment/rules.py` -- assignment rules (first match wins) and the rule file reader.
- `bauplan/plan.py` -- plan lines and the reader for `data/plan.csv`.
- `bauplan/sheets/` -- the Google Sheet: `google_auth.py` (service account tokens), `client.py`
  (Sheets API), `layout.py` (tabs, headers, formulas, formats; pure), `transactions_tab.py`
  (which rows to append and which empty cells to fill; pure), `service.py` (setup and sync).
- `bauplan/dashboard/` -- the local HTML dashboard: `dataset.py` (sheet rows to page data;
  pure), `render.py` (inlines data and ECharts), `template.html` (all charts, filters and
  aggregation in the page), `vendor/echarts.min.js` (ECharts 5.5.1, Apache-2.0, from the npm
  package after checking its registry integrity).
- `bauplan/archive.py` -- the bank session and the raw bank responses on disk, written once.
- `bauplan/sync.py` -- fetches all accounts of the session and archives before parsing.
- `bauplan/config.py` -- settings from the environment; `.env.example` lists them.
- `bauplan/cli.py` -- `import`, `sheet-setup`, `sheet-sync`, `dashboard`, `connect`, `accounts`,
  `fetch`.
- `docs/setup-google-sheet.md` -- one-time sheet setup and the monthly routine.
- `data/` (untracked) -- `imports/` (DKB exports), `transactions.csv`, `plan.csv` (plan lines with
  ids, migrated from the xlsx), `rules.csv` (assignment rules; lines marked `ZWEIFEL` need an
  answer from Max or Merle).

## Assigning transactions (v1, by Claude Code)

After `uv run bauplan import data/imports/<export>.csv`, apply `data/rules.csv` to the ledger and
look at the unassigned rows. Add a rule per counterparty, most specific first; short fragments
can hit other names ("Eni" is in "Koenigsbad"), so check per plan line which counterparties
landed there. Mark guesses with a note starting with `ZWEIFEL:`.
- `docs/setup-enable-banking.md` -- one-time bank setup.

## Commands

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
set -a && source .env && set +a && uv run bauplan fetch
```

## Rules

- Raw bank responses are archived before anything parses them, and never overwritten.
- `data/`, `.env` and `*.pem` hold private data or keys and stay untracked.
- Tests use fakes (`httpx.MockTransport`, small fake classes), never the real bank.
